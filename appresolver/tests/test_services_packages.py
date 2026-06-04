from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from appresolver.backends import podman
from appresolver.environment import EnvironmentManifest
from appresolver.environment_registry import EnvironmentRegistry
from appresolver.errors import AppResolverError, CommandExecutionError, RegistryError
from appresolver.services.packages import install_package, remove_package
from appresolver.state import StatePaths


def save_environment_manifest(
    registry_dir: Path,
    status: str = "running",
) -> EnvironmentRegistry:
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


def test_install_package_service_tracks_after_success(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    registry_dir = tmp_path / ".appresolver" / "apps"
    environment_registry = save_environment_manifest(registry_dir, status="running")

    def fake_run_command(command: list[str]) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(args=command, returncode=0, stdout="", stderr="")

    monkeypatch.setattr(podman, "run_command", fake_run_command)

    result = install_package(environment_registry, "ubuntu-24.04-default", "curl", execute=True)

    packages = environment_registry.load("ubuntu-24.04-default").installed_packages()
    assert result.output["tracked"] is True
    assert packages[0]["name"] == "curl"
    assert packages[0]["manager"] == "apt"


def test_install_package_service_plan_only_does_not_call_subprocess_or_mutate(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    registry_dir = tmp_path / ".appresolver" / "apps"
    environment_registry = save_environment_manifest(registry_dir, status="running")

    def fail_run_command(command: list[str]) -> subprocess.CompletedProcess[str]:
        raise AssertionError("plan-only service call must not call subprocess")

    monkeypatch.setattr(podman, "run_command", fail_run_command)

    result = install_package(environment_registry, "ubuntu-24.04-default", "curl", execute=False)

    assert result.output["status"] == "planned-install"
    assert environment_registry.load("ubuntu-24.04-default").installed_packages() == []


def test_remove_package_service_untracks_after_success(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    registry_dir = tmp_path / ".appresolver" / "apps"
    environment_registry = save_environment_manifest(registry_dir, status="running")
    manifest = environment_registry.load("ubuntu-24.04-default").with_installed_package(
        "curl", "apt", "2026-06-03T12:00:00+00:00"
    )
    environment_registry.update(manifest)

    def fake_run_command(command: list[str]) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(args=command, returncode=0, stdout="", stderr="")

    monkeypatch.setattr(podman, "run_command", fake_run_command)

    result = remove_package(environment_registry, "ubuntu-24.04-default", "curl", execute=True)

    assert result.output["tracked"] is False
    assert environment_registry.load("ubuntu-24.04-default").installed_packages() == []


def test_remove_package_service_apt_failure_leaves_tracking(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    registry_dir = tmp_path / ".appresolver" / "apps"
    environment_registry = save_environment_manifest(registry_dir, status="running")
    manifest = environment_registry.load("ubuntu-24.04-default").with_installed_package(
        "curl", "apt", "2026-06-03T12:00:00+00:00"
    )
    environment_registry.update(manifest)

    def fake_run_command(command: list[str]) -> subprocess.CompletedProcess[str]:
        raise CommandExecutionError("apt remove failed")

    monkeypatch.setattr(podman, "run_command", fake_run_command)

    with pytest.raises(CommandExecutionError):
        remove_package(environment_registry, "ubuntu-24.04-default", "curl", execute=True)

    assert environment_registry.load("ubuntu-24.04-default").installed_packages() == [
        {"name": "curl", "manager": "apt", "installed_at": "2026-06-03T12:00:00+00:00"}
    ]


def test_remove_package_service_registry_update_failure_warns_after_runtime_remove(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    registry_dir = tmp_path / ".appresolver" / "apps"
    environment_registry = save_environment_manifest(registry_dir, status="running")
    manifest = environment_registry.load("ubuntu-24.04-default").with_installed_package(
        "curl", "apt", "2026-06-03T12:00:00+00:00"
    )
    environment_registry.update(manifest)

    def fake_run_command(command: list[str]) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(args=command, returncode=0, stdout="", stderr="")

    def fail_update(self: EnvironmentRegistry, manifest: EnvironmentManifest) -> None:
        raise RegistryError("registry blocked")

    monkeypatch.setattr(podman, "run_command", fake_run_command)
    monkeypatch.setattr(EnvironmentRegistry, "update", fail_update)

    with pytest.raises(AppResolverError, match="runtime but registry tracking failed"):
        remove_package(environment_registry, "ubuntu-24.04-default", "curl", execute=True)
