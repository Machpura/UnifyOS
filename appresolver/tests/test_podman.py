from __future__ import annotations

import subprocess

import pytest

from appresolver.backends import podman
from appresolver.backends.podman import (
    execute_plan,
    inspect_environment_runtime,
    plan_destroy_environment,
    plan_environment,
    plan_start_environment,
    plan_stop_environment,
)
from appresolver.environment import EnvironmentManifest
from appresolver.errors import BackendError, CommandExecutionError


def make_environment_manifest(
    environment_id: str = "ubuntu-24.04-default",
    backend: str = "container",
    image: str = "ubuntu:24.04",
    status: str = "defined",
) -> EnvironmentManifest:
    return EnvironmentManifest(
        environment_id=environment_id,
        name=environment_id,
        backend=backend,
        image=image,
        status=status,
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


def test_plan_destroy_environment_returns_expected_podman_action() -> None:
    plan = plan_destroy_environment(make_environment_manifest(status="created"))

    assert plan.environment_id == "ubuntu-24.04-default"
    assert plan.backend == "podman"
    assert [action.id for action in plan.actions] == ["remove-container"]
    assert plan.actions[0].description == "Remove managed environment container"
    assert plan.actions[0].command == ["podman", "rm", "appresolver-env-ubuntu-24.04-default"]


def test_plan_destroy_environment_commands_are_lists_not_shell_strings() -> None:
    plan = plan_destroy_environment(make_environment_manifest(status="created"))

    for action in plan.actions:
        assert isinstance(action.command, list)
        assert all(isinstance(part, str) for part in action.command)


def test_plan_destroy_environment_to_dict_keeps_command_arrays() -> None:
    plan = plan_destroy_environment(make_environment_manifest(status="created"))

    output = plan.to_dict()

    assert output["actions"][0]["command"] == ["podman", "rm", "appresolver-env-ubuntu-24.04-default"]


def test_plan_destroy_environment_rejects_non_container_backend() -> None:
    with pytest.raises(BackendError, match="backend 'container'"):
        plan_destroy_environment(make_environment_manifest(backend="flatpak", status="created"))


def test_plan_start_environment_returns_expected_podman_action() -> None:
    plan = plan_start_environment(make_environment_manifest(status="created"))

    assert plan.environment_id == "ubuntu-24.04-default"
    assert plan.backend == "podman"
    assert [action.id for action in plan.actions] == ["start-container"]
    assert plan.actions[0].description == "Start managed environment container"
    assert plan.actions[0].command == ["podman", "start", "appresolver-env-ubuntu-24.04-default"]


def test_plan_start_environment_commands_are_lists_not_shell_strings() -> None:
    plan = plan_start_environment(make_environment_manifest(status="created"))

    for action in plan.actions:
        assert isinstance(action.command, list)
        assert all(isinstance(part, str) for part in action.command)


def test_plan_start_environment_to_dict_keeps_command_arrays() -> None:
    plan = plan_start_environment(make_environment_manifest(status="created"))

    output = plan.to_dict()

    assert output["actions"][0]["command"] == ["podman", "start", "appresolver-env-ubuntu-24.04-default"]


def test_plan_start_environment_rejects_non_container_backend() -> None:
    with pytest.raises(BackendError, match="backend 'container'"):
        plan_start_environment(make_environment_manifest(backend="flatpak", status="created"))


def test_plan_stop_environment_returns_expected_podman_action() -> None:
    plan = plan_stop_environment(make_environment_manifest(status="running"))

    assert plan.environment_id == "ubuntu-24.04-default"
    assert plan.backend == "podman"
    assert [action.id for action in plan.actions] == ["stop-container"]
    assert plan.actions[0].description == "Stop managed environment container"
    assert plan.actions[0].command == ["podman", "stop", "appresolver-env-ubuntu-24.04-default"]


def test_plan_stop_environment_commands_are_lists_not_shell_strings() -> None:
    plan = plan_stop_environment(make_environment_manifest(status="running"))

    for action in plan.actions:
        assert isinstance(action.command, list)
        assert all(isinstance(part, str) for part in action.command)


def test_plan_stop_environment_to_dict_keeps_command_arrays() -> None:
    plan = plan_stop_environment(make_environment_manifest(status="running"))

    output = plan.to_dict()

    assert output["actions"][0]["command"] == ["podman", "stop", "appresolver-env-ubuntu-24.04-default"]


def test_plan_stop_environment_rejects_non_container_backend() -> None:
    with pytest.raises(BackendError, match="backend 'container'"):
        plan_stop_environment(make_environment_manifest(backend="flatpak", status="running"))


def test_execute_plan_calls_central_runner_with_planned_commands(monkeypatch: pytest.MonkeyPatch) -> None:
    plan = plan_environment(make_environment_manifest())
    calls: list[list[str]] = []

    def fake_run_command(command: list[str]) -> object:
        calls.append(command)
        return object()

    monkeypatch.setattr(podman, "run_command", fake_run_command)

    execute_plan(plan)

    assert calls == [action.command for action in plan.actions]


def test_inspect_environment_runtime_detects_running_container(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run_command(command: list[str]) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            args=command,
            returncode=0,
            stdout='[{"State": {"Running": true, "Status": "running"}}]',
            stderr="",
        )

    monkeypatch.setattr(podman, "run_command", fake_run_command)

    inspection = inspect_environment_runtime(make_environment_manifest(status="created"))

    assert inspection.runtime_status == "running"


def test_inspect_environment_runtime_detects_stopped_container(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run_command(command: list[str]) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            args=command,
            returncode=0,
            stdout='[{"State": {"Running": false, "Status": "exited"}}]',
            stderr="",
        )

    monkeypatch.setattr(podman, "run_command", fake_run_command)

    inspection = inspect_environment_runtime(make_environment_manifest(status="running"))

    assert inspection.runtime_status == "stopped"


def test_inspect_environment_runtime_treats_no_such_container_as_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_run_command(command: list[str]) -> subprocess.CompletedProcess[str]:
        raise CommandExecutionError("Error: no such container appresolver-env-ubuntu-24.04-default")

    monkeypatch.setattr(podman, "run_command", fake_run_command)

    inspection = inspect_environment_runtime(make_environment_manifest(status="created"))

    assert inspection.runtime_status == "missing"


def test_inspect_environment_runtime_rejects_unexpected_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run_command(command: list[str]) -> subprocess.CompletedProcess[str]:
        raise CommandExecutionError("permission denied")

    monkeypatch.setattr(podman, "run_command", fake_run_command)

    with pytest.raises(CommandExecutionError, match="permission denied"):
        inspect_environment_runtime(make_environment_manifest(status="created"))


def test_inspect_environment_runtime_rejects_invalid_json(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run_command(command: list[str]) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(args=command, returncode=0, stdout="{", stderr="")

    monkeypatch.setattr(podman, "run_command", fake_run_command)

    with pytest.raises(BackendError, match="invalid JSON"):
        inspect_environment_runtime(make_environment_manifest(status="created"))


def test_inspect_environment_runtime_rejects_non_container_backend() -> None:
    with pytest.raises(BackendError, match="backend 'container'"):
        inspect_environment_runtime(make_environment_manifest(backend="flatpak", status="created"))
