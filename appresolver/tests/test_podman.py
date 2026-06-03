from __future__ import annotations

import pytest

from appresolver.backends.podman import plan_environment
from appresolver.environment import EnvironmentManifest
from appresolver.errors import BackendError


def make_environment_manifest(
    environment_id: str = "ubuntu-24.04-default",
    backend: str = "container",
    image: str = "ubuntu:24.04",
) -> EnvironmentManifest:
    return EnvironmentManifest(
        environment_id=environment_id,
        name=environment_id,
        backend=backend,
        image=image,
        status="defined",
        created_at="2026-06-03T12:00:00+00:00",
        permissions={},
        apps=[],
        source={"type": "manual"},
    )


def test_plan_environment_returns_expected_podman_actions() -> None:
    plan = plan_environment(make_environment_manifest())

    assert plan.environment_id == "ubuntu-24.04-default"
    assert plan.backend == "podman"
    assert [action.id for action in plan.actions] == ["pull-image", "create-container"]
    assert plan.actions[0].command == ["podman", "pull", "ubuntu:24.04"]
    assert plan.actions[1].command == [
        "podman",
        "create",
        "--name",
        "appresolver-env-ubuntu-24.04-default",
        "--label",
        "appresolver.environment_id=ubuntu-24.04-default",
        "ubuntu:24.04",
        "sleep",
        "infinity",
    ]


def test_plan_environment_commands_are_lists_not_shell_strings() -> None:
    plan = plan_environment(make_environment_manifest())

    for action in plan.actions:
        assert isinstance(action.command, list)
        assert all(isinstance(part, str) for part in action.command)


def test_plan_environment_to_dict_keeps_command_arrays() -> None:
    plan = plan_environment(make_environment_manifest())

    output = plan.to_dict()

    assert output["actions"][0]["command"] == ["podman", "pull", "ubuntu:24.04"]


def test_plan_environment_rejects_non_container_backend() -> None:
    with pytest.raises(BackendError, match="backend 'container'"):
        plan_environment(make_environment_manifest(backend="flatpak"))

