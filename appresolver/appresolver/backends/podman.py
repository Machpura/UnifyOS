from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Any

from appresolver.environment import EnvironmentManifest
from appresolver.errors import BackendError, CommandExecutionError
from appresolver.subprocess_runner import run_command


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
class RuntimeInspection:
    environment_id: str
    runtime_status: str


def plan_environment(manifest: EnvironmentManifest) -> PodmanPlan:
    if manifest.backend != "container":
        raise BackendError(
            f"Podman planning requires environment backend 'container', got '{manifest.backend}'"
        )

    container_name = f"appresolver-env-{manifest.environment_id}"
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

    container_name = f"appresolver-env-{manifest.environment_id}"
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

    container_name = f"appresolver-env-{manifest.environment_id}"
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

    container_name = f"appresolver-env-{manifest.environment_id}"
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


def inspect_environment_runtime(manifest: EnvironmentManifest) -> RuntimeInspection:
    if manifest.backend != "container":
        raise BackendError(
            f"Podman runtime inspection requires environment backend 'container', got '{manifest.backend}'"
        )

    container_name = f"appresolver-env-{manifest.environment_id}"
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
        or "no container with name or id" in normalized
        or "does not exist" in normalized
    )


def execute_plan(plan: PodmanPlan) -> None:
    for action in plan.actions:
        run_command(action.command)
