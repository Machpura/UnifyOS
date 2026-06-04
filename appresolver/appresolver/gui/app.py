from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, Qt, QThread, Signal, Slot
from PySide6.QtWidgets import (
    QApplication,
    QAbstractItemView,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from appresolver.environment_registry import EnvironmentRegistry
from appresolver.errors import AppResolverError
from appresolver.gui.helpers import format_actions, format_error, format_packages, format_result
from appresolver.services import environments as environment_services
from appresolver.services import packages as package_services
from appresolver.services import summaries as summary_services
from appresolver.state import StatePaths


class Worker(QObject):
    result = Signal(object)
    error = Signal(object)
    finished = Signal()

    def __init__(self, task: Callable[[], Any]) -> None:
        super().__init__()
        self.task = task

    @Slot()
    def run(self) -> None:
        try:
            self.result.emit(self.task())
        except Exception as exc:  # noqa: BLE001 - surfaced to the GUI log.
            self.error.emit(exc)
        finally:
            self.finished.emit()


class AppResolverWindow(QMainWindow):
    def __init__(self, registry_dir: Path) -> None:
        super().__init__()
        self.registry_dir = registry_dir
        self.state_paths = StatePaths.from_registry_dir(registry_dir)
        self.environment_registry = EnvironmentRegistry(self.state_paths.environments_dir)
        self.worker_thread: QThread | None = None
        self.worker: Worker | None = None
        self.action_buttons: list[QPushButton] = []

        self.setWindowTitle("App Resolver")
        self.resize(1100, 720)
        self.setCentralWidget(self.build_ui())
        self.refresh_environments()

    def build_ui(self) -> QWidget:
        root = QWidget()
        root_layout = QVBoxLayout(root)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        root_layout.addWidget(splitter, 1)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.clicked.connect(self.refresh_environments)
        self.environment_list = QListWidget()
        self.environment_list.currentItemChanged.connect(self.environment_selected)
        left_layout.addWidget(self.refresh_button)
        left_layout.addWidget(self.environment_list, 1)
        splitter.addWidget(left)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.addWidget(self.build_summary_group())
        right_layout.addWidget(self.build_package_group())
        right_layout.addWidget(self.build_action_group())
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)

        self.details = QPlainTextEdit()
        self.details.setReadOnly(True)
        self.details.setPlaceholderText("Action details and errors")
        root_layout.addWidget(self.details, 1)
        return root

    def build_summary_group(self) -> QGroupBox:
        group = QGroupBox("Environment Summary")
        layout = QGridLayout(group)
        self.summary_labels: dict[str, QLabel] = {}
        rows = [
            ("environment_id", "Environment"),
            ("name", "Name"),
            ("image", "Image"),
            ("manifest_status", "Manifest"),
            ("runtime_status", "Runtime"),
            ("consistent", "Consistent"),
            ("suggested_status", "Suggested"),
            ("available_actions", "Available"),
        ]
        for row, (key, label) in enumerate(rows):
            layout.addWidget(QLabel(label), row, 0)
            value = QLabel("")
            value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            value.setWordWrap(True)
            self.summary_labels[key] = value
            layout.addWidget(value, row, 1)
        return group

    def build_package_group(self) -> QGroupBox:
        group = QGroupBox("Tracked Packages")
        layout = QVBoxLayout(group)
        self.package_list = QListWidget()
        self.package_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        layout.addWidget(self.package_list)

        input_row = QHBoxLayout()
        self.package_input = QLineEdit()
        self.package_input.setPlaceholderText("Package name")
        input_row.addWidget(self.package_input, 1)
        self.plan_install_button = self.add_action_button("Plan Install", self.plan_install_package)
        self.execute_install_button = self.add_action_button("Install", self.execute_install_package)
        input_row.addWidget(self.plan_install_button)
        input_row.addWidget(self.execute_install_button)
        layout.addLayout(input_row)

        remove_row = QHBoxLayout()
        self.plan_remove_button = self.add_action_button("Plan Remove Selected", self.plan_remove_package)
        self.execute_remove_button = self.add_action_button("Remove Selected", self.execute_remove_package)
        remove_row.addWidget(self.plan_remove_button)
        remove_row.addWidget(self.execute_remove_button)
        remove_row.addStretch(1)
        layout.addLayout(remove_row)
        return group

    def build_action_group(self) -> QGroupBox:
        group = QGroupBox("Environment Actions")
        layout = QGridLayout(group)
        buttons = [
            ("Plan Create", self.plan_create),
            ("Create", self.execute_create),
            ("Plan Start", self.plan_start),
            ("Start", self.execute_start),
            ("Plan Stop", self.plan_stop),
            ("Stop", self.execute_stop),
            ("Plan Destroy", self.plan_destroy),
            ("Destroy", self.execute_destroy),
            ("Inspect", self.inspect_environment),
            ("Plan Reconcile", self.plan_reconcile),
            ("Reconcile", self.execute_reconcile),
        ]
        for index, (label, callback) in enumerate(buttons):
            button = self.add_action_button(label, callback)
            layout.addWidget(button, index // 4, index % 4)
        return group

    def add_action_button(self, label: str, callback: Callable[[], None]) -> QPushButton:
        button = QPushButton(label)
        button.clicked.connect(callback)
        self.action_buttons.append(button)
        return button

    def refresh_environments(self) -> None:
        current_id = self.selected_environment_id()
        self.environment_list.clear()
        try:
            manifests = environment_services.list_environments(self.environment_registry)
        except AppResolverError as exc:
            self.show_error(exc)
            return

        selected_row = 0
        for index, manifest in enumerate(manifests):
            item = QListWidgetItem(f"{manifest.environment_id}\t{manifest.status}")
            item.setData(Qt.ItemDataRole.UserRole, manifest.environment_id)
            self.environment_list.addItem(item)
            if manifest.environment_id == current_id:
                selected_row = index
        if manifests:
            self.environment_list.setCurrentRow(selected_row)
        else:
            self.clear_summary()
            self.package_list.clear()

    def environment_selected(self, current: QListWidgetItem | None, previous: QListWidgetItem | None) -> None:
        if current is None:
            return
        self.load_selected_environment()

    def load_selected_environment(self) -> None:
        environment_id = self.require_selected_environment()
        if environment_id is None:
            return
        try:
            manifest = environment_services.load_environment(self.environment_registry, environment_id)
            summary = summary_services.environment_summary_result(manifest)
            packages = package_services.tracked_packages(self.environment_registry, environment_id)
        except AppResolverError as exc:
            self.show_error(exc)
            return
        self.show_summary(summary)
        self.show_packages(packages)

    def selected_environment_id(self) -> str | None:
        item = self.environment_list.currentItem()
        if item is None:
            return None
        value = item.data(Qt.ItemDataRole.UserRole)
        return str(value) if value is not None else None

    def require_selected_environment(self) -> str | None:
        environment_id = self.selected_environment_id()
        if environment_id is None:
            self.show_error(ValueError("select an environment first"))
            return None
        return environment_id

    def selected_package_name(self) -> str | None:
        item = self.package_list.currentItem()
        if item is None:
            self.show_error(ValueError("select a package first"))
            return None
        value = item.data(Qt.ItemDataRole.UserRole)
        return str(value) if value is not None else None

    def typed_package_name(self) -> str | None:
        package_name = self.package_input.text().strip()
        if not package_name:
            self.show_error(ValueError("enter a package name first"))
            return None
        return package_name

    def show_summary(self, summary: dict[str, object]) -> None:
        for key, label in self.summary_labels.items():
            value = summary.get(key, "")
            if isinstance(value, list):
                label.setText(", ".join(str(item) for item in value) or "none")
            else:
                label.setText(str(value))

    def clear_summary(self) -> None:
        for label in self.summary_labels.values():
            label.setText("")

    def show_packages(self, packages: list[dict[str, str]]) -> None:
        self.package_list.clear()
        for package in packages:
            item = QListWidgetItem(package["name"])
            item.setData(Qt.ItemDataRole.UserRole, package["name"])
            self.package_list.addItem(item)

    def plan_create(self) -> None:
        self.plan_environment_action(lambda env_id: environment_services.create_environment(self.environment_registry, env_id, False))

    def execute_create(self) -> None:
        self.execute_environment_action(
            "Create environment runtime?",
            lambda env_id: environment_services.create_environment(self.environment_registry, env_id, True),
        )

    def plan_start(self) -> None:
        self.plan_environment_action(lambda env_id: environment_services.start_environment(self.environment_registry, env_id, False))

    def execute_start(self) -> None:
        self.execute_environment_action(
            "Start environment runtime?",
            lambda env_id: environment_services.start_environment(self.environment_registry, env_id, True),
        )

    def plan_stop(self) -> None:
        self.plan_environment_action(lambda env_id: environment_services.stop_environment(self.environment_registry, env_id, False))

    def execute_stop(self) -> None:
        self.execute_environment_action(
            "Stop environment runtime?",
            lambda env_id: environment_services.stop_environment(self.environment_registry, env_id, True),
        )

    def plan_destroy(self) -> None:
        self.plan_environment_action(lambda env_id: environment_services.destroy_environment(self.environment_registry, env_id, False))

    def execute_destroy(self) -> None:
        self.execute_environment_action(
            "Destroy environment runtime?",
            lambda env_id: environment_services.destroy_environment(self.environment_registry, env_id, True),
        )

    def inspect_environment(self) -> None:
        environment_id = self.require_selected_environment()
        if environment_id is None:
            return
        try:
            result = environment_services.inspect_environment(self.environment_registry, environment_id)
        except AppResolverError as exc:
            self.show_error(exc)
            return
        self.show_details(result)

    def plan_reconcile(self) -> None:
        self.plan_environment_action(lambda env_id: environment_services.reconcile_environment(self.environment_registry, env_id, False))

    def execute_reconcile(self) -> None:
        self.execute_environment_action(
            "Reconcile manifest status with runtime state?",
            lambda env_id: environment_services.reconcile_environment(self.environment_registry, env_id, True),
        )

    def plan_install_package(self) -> None:
        environment_id = self.require_selected_environment()
        package_name = self.typed_package_name()
        if environment_id is None or package_name is None:
            return
        try:
            result = package_services.install_package(self.environment_registry, environment_id, package_name, False)
        except AppResolverError as exc:
            self.show_error(exc)
            return
        self.show_details(result.output)

    def execute_install_package(self) -> None:
        environment_id = self.require_selected_environment()
        package_name = self.typed_package_name()
        if environment_id is None or package_name is None:
            return
        self.execute_action(
            f"Install package '{package_name}'?",
            lambda: package_services.install_package(self.environment_registry, environment_id, package_name, True),
        )

    def plan_remove_package(self) -> None:
        environment_id = self.require_selected_environment()
        package_name = self.selected_package_name()
        if environment_id is None or package_name is None:
            return
        try:
            result = package_services.remove_package(self.environment_registry, environment_id, package_name, False)
        except AppResolverError as exc:
            self.show_error(exc)
            return
        self.show_details(result.output)

    def execute_remove_package(self) -> None:
        environment_id = self.require_selected_environment()
        package_name = self.selected_package_name()
        if environment_id is None or package_name is None:
            return
        self.execute_action(
            f"Remove package '{package_name}'?",
            lambda: package_services.remove_package(self.environment_registry, environment_id, package_name, True),
        )

    def plan_environment_action(self, task_factory: Callable[[str], Any]) -> None:
        environment_id = self.require_selected_environment()
        if environment_id is None:
            return
        try:
            result = task_factory(environment_id)
        except AppResolverError as exc:
            self.show_error(exc)
            return
        if hasattr(result, "output"):
            self.show_details(result.output)
        else:
            self.show_details(result)

    def execute_environment_action(self, prompt: str, task_factory: Callable[[str], Any]) -> None:
        environment_id = self.require_selected_environment()
        if environment_id is None:
            return
        self.execute_action(prompt, lambda: task_factory(environment_id))

    def execute_action(self, prompt: str, task: Callable[[], Any]) -> None:
        if QMessageBox.question(
            self,
            "Confirm Execute Action",
            prompt,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        ) != QMessageBox.StandardButton.Yes:
            return

        self.set_actions_enabled(False)
        self.details.setPlainText("Running...")
        thread = QThread(self)
        worker = Worker(task)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.result.connect(self.worker_result)
        worker.error.connect(self.worker_error)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self.worker_finished)
        self.worker_thread = thread
        self.worker = worker
        thread.start()

    @Slot(object)
    def worker_result(self, result: object) -> None:
        output = getattr(result, "output", result)
        self.show_details(output)

    @Slot(object)
    def worker_error(self, error: object) -> None:
        if isinstance(error, BaseException):
            self.show_error(error)
        else:
            self.details.setPlainText(f"error: {error}")

    @Slot()
    def worker_finished(self) -> None:
        self.worker = None
        self.worker_thread = None
        self.set_actions_enabled(True)
        self.refresh_environments()

    def set_actions_enabled(self, enabled: bool) -> None:
        self.refresh_button.setEnabled(enabled)
        self.environment_list.setEnabled(enabled)
        self.package_input.setEnabled(enabled)
        self.package_list.setEnabled(enabled)
        for button in self.action_buttons:
            button.setEnabled(enabled)

    def show_details(self, result: object) -> None:
        if hasattr(result, "output"):
            result = getattr(result, "output")
        if isinstance(result, dict) and isinstance(result.get("actions"), list):
            text = format_result(result)
            actions = result.get("actions", [])
            if actions:
                text = f"{text}\n\nCommands:\n{format_actions(actions)}"
            self.details.setPlainText(text)
        elif isinstance(result, list):
            self.details.setPlainText(format_packages(result) if all(isinstance(item, dict) for item in result) else format_result(result))
        else:
            self.details.setPlainText(format_result(result))

    def show_error(self, error: BaseException) -> None:
        self.details.setPlainText(format_error(error))


def run_gui(registry_dir: Path) -> int:
    app = QApplication([])
    window = AppResolverWindow(registry_dir)
    window.show()
    return app.exec()
