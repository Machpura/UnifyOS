from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from appresolver.backends import podman
from appresolver.environment import EnvironmentManifest
from appresolver.environment_registry import EnvironmentRegistry
from appresolver.errors import CommandExecutionError
from appresolver.services.environments import reconcile_environment
from appresolver.state import StatePaths


def save_environment_manifest(registry_dir: Path, status: str = "defined") -> EnvironmentRegistry:
    environment_registry = EnvironmentRegistry(StatePaths.from_registry_dir(registry_dir).environments_dir)
    environment_registry.save(
        EnvironmentManifest(
            environment_id="ubuntu-24.04-default",
            name="ubuntu-24.04-default",
            backend="container",
            image="ubuntu:24.04",
            status=status,
            created_at="2026-06-03T12:00:00+00:00",
            permissions={},
            apps=[],
            source={"type": "manual"},
        )
    )
    return environment_registry


def test_reconcile_environment_service_consistent_defined_missing_is_noop(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    registry_dir = tmp_path / ".appresolver" / "apps"
    environment_registry = save_environment_manifest(registry_dir, status="defined")

    def fake_run_command(command: list[str]) -> subprocess.CompletedProcess[str]:
        raise CommandExecutionError('Error: no such object: "appresolver-env-ubuntu-24.04-default"')

    monkeypatch.setattr(podman, "run_command", fake_run_command)

    result = reconcile_environment(environment_registry, "ubuntu-24.04-default", execute=True)

    assert result == {
        "environment_id": "ubuntu-24.04-default",
        "manifest_status": "defined",
        "runtime_status": "missing",
        "consistent": True,
        "suggested_status": "defined",
        "executed": False,
    }
    assert environment_registry.load("ubuntu-24.04-default").status == "defined"


def test_reconcile_environment_service_execute_updates_manifest(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    registry_dir = tmp_path / ".appresolver" / "apps"
    environment_registry = save_environment_manifest(registry_dir, status="created")

    def fake_run_command(command: list[str]) -> subprocess.CompletedProcess[str]:
        raise CommandExecutionError('Error: no such object: "appresolver-env-ubuntu-24.04-default"')

    monkeypatch.setattr(podman, "run_command", fake_run_command)

    result = reconcile_environment(environment_registry, "ubuntu-24.04-default", execute=True)

    assert result == {
        "environment_id": "ubuntu-24.04-default",
        "previous_status": "created",
        "runtime_status": "missing",
        "new_status": "defined",
        "executed": True,
    }
    assert environment_registry.load("ubuntu-24.04-default").status == "defined"
