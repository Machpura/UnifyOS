from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from appresolver.environment import EnvironmentManifest
from appresolver.errors import BackendError
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


def execute_plan(plan: PodmanPlan) -> None:
    for action in plan.actions:
        run_command(action.command)
