from __future__ import annotations

from pathlib import Path

import pytest

from appresolver.environment import EnvironmentManifest
from appresolver.environment_registry import EnvironmentRegistry
from appresolver.errors import AppNotFoundError, InvalidAppIdError
from appresolver.state import StatePaths


def make_environment_manifest(environment_id: str = "ubuntu-24.04-default") -> EnvironmentManifest:
    return EnvironmentManifest(
        environment_id=environment_id,
        name=environment_id,
        backend="container",
        image="ubuntu:24.04",
        status="defined",
        created_at="2026-06-03T12:00:00+00:00",
        permissions={},
        apps=[],
        source={"type": "manual"},
    )


def test_environment_registry_saves_manifest_with_safe_filename(tmp_path: Path) -> None:
    state_paths = StatePaths.from_registry_dir(tmp_path / ".appresolver" / "apps")
    registry = EnvironmentRegistry(state_paths.environments_dir)
    manifest = make_environment_manifest("ubuntu-24.04-default")

    registry.save(manifest)

    assert (state_paths.environments_dir / "ubuntu-24.04-default.json").exists()


def test_environment_registry_loads_saved_manifest(tmp_path: Path) -> None:
    registry = EnvironmentRegistry(tmp_path)
    manifest = make_environment_manifest()
    registry.save(manifest)

    loaded = registry.load(manifest.environment_id)

    assert loaded == manifest


def test_environment_registry_lists_manifests_sorted_by_environment_id(tmp_path: Path) -> None:
    registry = EnvironmentRegistry(tmp_path)
    registry.save(make_environment_manifest("ubuntu-24.04-default"))
    registry.save(make_environment_manifest("fedora-latest"))
    registry.save(make_environment_manifest("arch-community"))

    environment_ids = [manifest.environment_id for manifest in registry.list()]

    assert environment_ids == ["arch-community", "fedora-latest", "ubuntu-24.04-default"]


def test_environment_registry_delete_removes_manifest(tmp_path: Path) -> None:
    registry = EnvironmentRegistry(tmp_path)
    manifest = make_environment_manifest()
    registry.save(manifest)

    registry.delete(manifest.environment_id)

    assert not registry.exists(manifest.environment_id)


def test_environment_registry_delete_missing_manifest_raises_clear_error(tmp_path: Path) -> None:
    registry = EnvironmentRegistry(tmp_path)

    with pytest.raises(AppNotFoundError, match="not managed"):
        registry.delete("ubuntu-24.04-default")


def test_environment_registry_load_missing_manifest_raises_clear_error(tmp_path: Path) -> None:
    registry = EnvironmentRegistry(tmp_path)

    with pytest.raises(AppNotFoundError, match="not managed"):
        registry.load("ubuntu-24.04-default")


@pytest.mark.parametrize(
    "environment_id",
    [
        "",
        "../x",
        "a/b",
        "a\\b",
        ".hidden",
        "-bad",
        "bad env",
        "bad$env",
    ],
)
def test_environment_registry_rejects_unsafe_environment_ids(tmp_path: Path, environment_id: str) -> None:
    registry = EnvironmentRegistry(tmp_path)

    with pytest.raises(InvalidAppIdError):
        registry.path_for(environment_id)


def test_environment_registry_constructor_creates_no_directory(tmp_path: Path) -> None:
    environments_dir = tmp_path / ".appresolver" / "environments"

    EnvironmentRegistry(environments_dir)

    assert not environments_dir.exists()

