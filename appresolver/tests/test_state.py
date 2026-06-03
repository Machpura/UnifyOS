from __future__ import annotations

from pathlib import Path

import pytest

from appresolver.errors import BackendError
from appresolver.state import StatePaths


def test_default_state_paths_are_cwd_relative(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)

    state_paths = StatePaths.default()

    assert state_paths.state_root == tmp_path / ".appresolver"
    assert state_paths.apps_dir == tmp_path / ".appresolver" / "apps"
    assert state_paths.appimages_dir == tmp_path / ".appresolver" / "appimages"
    assert state_paths.launchers_dir == tmp_path / ".appresolver" / "launchers"
    assert state_paths.logs_dir == tmp_path / ".appresolver" / "logs"
    assert state_paths.environments_dir == tmp_path / ".appresolver" / "environments"


def test_state_paths_from_custom_registry_dir_derive_sibling_dirs(tmp_path: Path) -> None:
    registry_dir = tmp_path / "custom-state" / "apps"

    state_paths = StatePaths.from_registry_dir(registry_dir)

    assert state_paths.state_root == tmp_path / "custom-state"
    assert state_paths.apps_dir == tmp_path / "custom-state" / "apps"
    assert state_paths.appimages_dir == tmp_path / "custom-state" / "appimages"
    assert state_paths.launchers_dir == tmp_path / "custom-state" / "launchers"
    assert state_paths.logs_dir == tmp_path / "custom-state" / "logs"
    assert state_paths.environments_dir == tmp_path / "custom-state" / "environments"


def test_validate_inside_state_root_accepts_paths_under_state_root(tmp_path: Path) -> None:
    state_paths = StatePaths.from_registry_dir(tmp_path / "state" / "apps")

    path = state_paths.appimages_dir / "Example.AppImage"

    assert state_paths.validate_inside_state_root(path) == path.resolve(strict=False)


def test_validate_inside_state_root_rejects_paths_outside_state_root(tmp_path: Path) -> None:
    state_paths = StatePaths.from_registry_dir(tmp_path / "state" / "apps")

    with pytest.raises(BackendError, match="outside resolver state"):
        state_paths.validate_inside_state_root(tmp_path / "outside.AppImage")

