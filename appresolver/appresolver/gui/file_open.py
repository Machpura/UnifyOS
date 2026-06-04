from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QThread, Slot
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
)

from appresolver.errors import AppResolverError
from appresolver.gui.file_open_helpers import (
    build_file_open_view,
    execute_file_open,
    imported_app_details,
    plan_file_open,
)
from appresolver.gui.helpers import format_error, format_result
from appresolver.gui.workers import Worker
from appresolver.registry import AppRegistry
from appresolver.state import StatePaths


class FileOpenDialog(QDialog):
    def __init__(self, registry_dir: Path, path: Path) -> None:
        super().__init__()
        self.registry_dir = registry_dir
        self.state_paths = StatePaths.from_registry_dir(registry_dir)
        self.registry = AppRegistry(registry_dir)
        self.path = path
        self.plan_result: dict[str, object] | None = None
        self.worker_thread: QThread | None = None
        self.worker: Worker | None = None
        self.labels: dict[str, QLabel] = {}

        self.setWindowTitle("Open With App Resolver")
        self.resize(720, 560)
        self.build_ui()
        self.load_plan()

    def build_ui(self) -> None:
        layout = QVBoxLayout(self)
        self.title_label = QLabel("")
        self.title_label.setWordWrap(True)
        self.title_label.setStyleSheet("font-size: 18px; font-weight: 600;")
        layout.addWidget(self.title_label)

        grid = QGridLayout()
        fields = [
            ("full_path", "Path"),
            ("detected_type", "Detected type"),
            ("route", "Route"),
            ("supported_text", "Supported now"),
            ("status", "Status"),
            ("message", "Message"),
        ]
        for row, (key, label) in enumerate(fields):
            grid.addWidget(QLabel(label), row, 0)
            value = QLabel("")
            value.setWordWrap(True)
            value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            self.labels[key] = value
            grid.addWidget(value, row, 1)
        layout.addLayout(grid)

        self.safety_notes = QPlainTextEdit()
        self.safety_notes.setReadOnly(True)
        self.safety_notes.setMaximumHeight(90)
        layout.addWidget(QLabel("Safety notes"))
        layout.addWidget(self.safety_notes)

        self.actions = QPlainTextEdit()
        self.actions.setReadOnly(True)
        self.actions.setMaximumHeight(120)
        layout.addWidget(QLabel("Planned actions"))
        layout.addWidget(self.actions)

        self.details = QPlainTextEdit()
        self.details.setReadOnly(True)
        self.details.setPlaceholderText("Details and results")
        layout.addWidget(QLabel("Details"))
        layout.addWidget(self.details, 1)

        button_row = QHBoxLayout()
        button_row.addStretch(1)
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)
        self.action_button = QPushButton("Import")
        self.action_button.clicked.connect(self.execute_action)
        button_row.addWidget(self.cancel_button)
        button_row.addWidget(self.action_button)
        layout.addLayout(button_row)

    def load_plan(self) -> None:
        try:
            result = plan_file_open(self.registry, self.state_paths, self.path)
        except AppResolverError as exc:
            self.plan_result = None
            self.title_label.setText(self.path.name)
            self.labels["full_path"].setText(str(self.path))
            self.labels["detected_type"].setText("unknown")
            self.labels["route"].setText("unsupported")
            self.labels["supported_text"].setText("no")
            self.labels["status"].setText("error")
            self.labels["message"].setText(str(exc))
            self.safety_notes.setPlainText("App Resolver could not inspect this file.")
            self.actions.setPlainText("No planned actions.")
            self.details.setPlainText(format_error(exc))
            self.action_button.setVisible(False)
            return

        self.plan_result = result
        self.show_view(build_file_open_view(result))
        self.details.setPlainText(format_result(result))

    def show_view(self, view: dict[str, object]) -> None:
        self.title_label.setText(str(view["file_name"]))
        for key, label in self.labels.items():
            label.setText(str(view[key]))
        self.safety_notes.setPlainText("\n".join(str(note) for note in view["safety_notes"]))
        planned_actions = view["planned_actions"]
        if isinstance(planned_actions, list) and planned_actions:
            self.actions.setPlainText("\n".join(str(action) for action in planned_actions))
        else:
            self.actions.setPlainText("No planned actions.")
        can_execute = bool(view["can_execute"])
        self.action_button.setVisible(can_execute)
        self.action_button.setEnabled(can_execute)
        if can_execute:
            self.action_button.setText(str(view["action_label"]))

    def execute_action(self) -> None:
        self.set_running(True)
        self.details.setPlainText("Running...")
        thread = QThread(self)
        worker = Worker(lambda: execute_file_open(self.registry, self.state_paths, self.path))
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
        if isinstance(result, dict):
            lines = ["Import completed.", *imported_app_details(result), "", format_result(result)]
            self.details.setPlainText("\n".join(line for line in lines if line != ""))
            self.labels["status"].setText(str(result.get("status", "imported")))
        else:
            self.details.setPlainText(format_result(result))

    @Slot(object)
    def worker_error(self, error: object) -> None:
        if isinstance(error, BaseException):
            self.details.setPlainText(format_error(error))
        else:
            self.details.setPlainText(f"error: {error}")

    @Slot()
    def worker_finished(self) -> None:
        self.worker = None
        self.worker_thread = None
        self.set_running(False)

    def set_running(self, running: bool) -> None:
        self.action_button.setEnabled(not running)
        self.cancel_button.setEnabled(not running)


def run_file_open_gui(registry_dir: Path, path: Path) -> int:
    app = QApplication([])
    dialog = FileOpenDialog(registry_dir, path)
    dialog.show()
    return app.exec()
