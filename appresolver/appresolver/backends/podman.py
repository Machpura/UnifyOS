from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from typing import Any

from appresolver.environment import EnvironmentManifest
from appresolver.errors import BackendError, CommandExecutionError
from appresolver.subprocess_runner import run_command


PACKAGE_NAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9+._:-]*$")
PACKAGE_INSTALL_STATUSES = {"created", "running", "stopped"}


@dataclass(frozen=True)
class PlannedAction:
    id: str
    description: str
    command: list[str]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class PodmanPlan:
    environment_id: str
    backend: str
    actions: list[PlannedAction]

    def to_dict(self) -> dict[str, Any]:
        return {
            "environment_id": self.environment_id,
            "backend": self.backend,
            "actions": [action.to_dict() for action in self.actions],
        }


@dataclass(frozen=True)
class PackageInstallPlan:
    environment_id: str
    package: str
    package_manager: str
    actions: list[PlannedAction]

    def to_dict(self) -> dict[str, Any]:
        return {
            "environment_id": self.environment_id,
            "package": self.package,
            "package_manager": self.package_manager,
            "actions": [action.to_dict() for action in self.actions],
        }


@dataclass(frozen=True)
class RuntimeInspection:
    environment_id: str
    runtime_status: str


def container_name_for_environment(manifest: EnvironmentManifest) -> str:
    return f"appresolver-env-{manifest.environment_id}"


def plan_environment(manifest: EnvironmentManifest) -> PodmanPlan:
    if manifest.backend != "container":
        raise BackendError(
            f"Podman planning requires environment backend 'container', got '{manifest.backend}'"
        )

    container_name = container_name_for_environment(manifest)
    return PodmanPlan(
        environment_id=manifest.environment_id,
        backend="podman",
        actions=[
            PlannedAction(
                id="pull-image",
                description="Pull container image",
                command=["podman", "pull", manifest.image],
            ),
            PlannedAction(
                id="create-container",
                description="Create managed environment container",
                command=[
                    "podman",
                    "create",
                    "--name",
                    container_name,
                    "--label",
                    f"appresolver.environment_id={manifest.environment_id}",
                    manifest.image,
                    "sleep",
                    "infinity",
                ],
            ),
        ],
    )


def plan_destroy_environment(manifest: EnvironmentManifest) -> PodmanPlan:
    if manifest.backend != "container":
        raise BackendError(
            f"Podman destroy planning requires environment backend 'container', got '{manifest.backend}'"
        )

    container_name = container_name_for_environment(manifest)
    return PodmanPlan(
        environment_id=manifest.environment_id,
        backend="podman",
        actions=[
            PlannedAction(
                id="remove-container",
                description="Remove managed environment container",
                command=["podman", "rm", container_name],
            )
        ],
    )


def plan_start_environment(manifest: EnvironmentManifest) -> PodmanPlan:
    if manifest.backend != "container":
        raise BackendError(
            f"Podman start planning requires environment backend 'container', got '{manifest.backend}'"
        )

    container_name = container_name_for_environment(manifest)
    return PodmanPlan(
        environment_id=manifest.environment_id,
        backend="podman",
        actions=[
            PlannedAction(
                id="start-container",
                description="Start managed environment container",
                command=["podman", "start", container_name],
            )
        ],
    )


def plan_stop_environment(manifest: EnvironmentManifest) -> PodmanPlan:
    if manifest.backend != "container":
        raise BackendError(
            f"Podman stop planning requires environment backend 'container', got '{manifest.backend}'"
        )

    container_name = container_name_for_environment(manifest)
    return PodmanPlan(
        environment_id=manifest.environment_id,
        backend="podman",
        actions=[
            PlannedAction(
                id="stop-container",
                description="Stop managed environment container",
                command=["podman", "stop", container_name],
            )
        ],
    )


def plan_install_package(manifest: EnvironmentManifest, package_name: str) -> PackageInstallPlan:
    if manifest.backend != "container":
        raise BackendError(
            f"Podman package install planning requires environment backend 'container', got '{manifest.backend}'"
        )
    if manifest.status not in PACKAGE_INSTALL_STATUSES:
        raise BackendError(
            f"environment '{manifest.environment_id}' status is '{manifest.status}'; "
            "package install requires status 'created', 'running', or 'stopped'"
        )

    validate_package_name(package_name)
    package_manager = detect_package_manager(manifest.image)
    container_name = container_name_for_environment(manifest)
    actions: list[PlannedAction] = []

    if manifest.status != "running":
        actions.append(
            PlannedAction(
                id="start-container",
                description="Start managed environment container",
                command=["podman", "start", container_name],
            )
        )

    if package_manager == "apt":
        actions.extend(
            [
                PlannedAction(
                    id="apt-update",
                    description="Update apt package metadata",
                    command=["podman", "exec", container_name, "apt-get", "update"],
                ),
                PlannedAction(
                    id="apt-install",
                    description="Install package with apt",
                    command=[
                        "podman",
                        "exec",
                        container_name,
                        "apt-get",
                        "install",
                        "-y",
                        package_name,
                    ],
                ),
            ]
        )

    return PackageInstallPlan(
        environment_id=manifest.environment_id,
        package=package_name,
        package_manager=package_manager,
        actions=actions,
    )


def validate_package_name(package_name: str) -> None:
    if not PACKAGE_NAME_PATTERN.fullmatch(package_name):
        raise BackendError(
            f"invalid package name '{package_name}'; expected pattern "
            r"^[A-Za-z0-9][A-Za-z0-9+._:-]*$"
        )


def detect_package_manager(image: str) -> str:
    normalized = image.lower()
    if normalized.startswith("ubuntu:") or normalized.startswith("debian:"):
        return "apt"
    raise BackendError(
        f"unsupported package manager for image '{image}'; v0 supports apt for ubuntu:* and debian:* images"
    )


def inspect_environment_runtime(manifest: EnvironmentManifest) -> RuntimeInspection:
    if manifest.backend != "container":
        raise BackendError(
            f"Podman runtime inspection requires environment backend 'container', got '{manifest.backend}'"
        )

    container_name = container_name_for_environment(manifest)
    try:
        result = run_command(["podman", "inspect", container_name])
    except CommandExecutionError as exc:
        if is_missing_container_error(str(exc)):
            return RuntimeInspection(environment_id=manifest.environment_id, runtime_status="missing")
        raise

    return RuntimeInspection(
        environment_id=manifest.environment_id,
        runtime_status=parse_inspect_runtime_status(result.stdout),
    )


def parse_inspect_runtime_status(output: str) -> str:
    try:
        data = json.loads(output)
    except json.JSONDecodeError as exc:
        raise BackendError(f"podman inspect returned invalid JSON: {exc}") from exc

    if isinstance(data, list) and data:
        container = data[0]
    elif isinstance(data, dict):
        container = data
    else:
        return "unknown"

    if not isinstance(container, dict):
        return "unknown"

    state = container.get("State")
    if not isinstance(state, dict):
        return "unknown"

    running = state.get("Running")
    if running is True:
        return "running"
    if running is False:
        return "stopped"

    status = state.get("Status")
    if isinstance(status, str) and status:
        if status.lower() == "running":
            return "running"
        return "stopped"

    return "unknown"


def is_missing_container_error(message: str) -> bool:
    normalized = message.lower()
    return (
        ("no such" in normalized and "container" in normalized)
        or "no such object" in normalized
        or "no container with name or id" in normalized
        or "no container with id or name" in normalized
        or "does not exist" in normalized
    )


def execute_actions(actions: list[PlannedAction]) -> None:
    for action in actions:
        run_command(action.command)


def execute_plan(plan: PodmanPlan) -> None:
    execute_actions(plan.actions)
