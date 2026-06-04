from __future__ import annotations

from pathlib import Path

import pytest

from appresolver.errors import AppResolverError
from appresolver.registry import AppRegistry
from appresolver.services import files
from appresolver.state import StatePaths


def write_file(path: Path, content: str = "#!/bin/sh\nexit 0\n") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


@pytest.mark.parametrize(
    ("filename", "detected_type"),
    [
        ("Example.AppImage", "appimage"),
        ("Example.appimage", "appimage"),
        ("Example.flatpakref", "flatpakref"),
        ("example.deb", "deb"),
        ("example.rpm", "rpm"),
        ("setup.exe", "windows-installer"),
        ("install.sh", "shell-script"),
        ("README.txt", "unknown"),
    ],
)
def test_detect_file_type(filename: str, detected_type: str) -> None:
    assert files.detect_file_type(Path(filename)) == detected_type


def test_open_path_rejects_missing_file(tmp_path: Path) -> None:
    registry_dir = tmp_path / ".appresolver" / "apps"

    with pytest.raises(AppResolverError, match="file does not exist"):
        files.open_path(
            AppRegistry(registry_dir),
            StatePaths.from_registry_dir(registry_dir),
            tmp_path / "missing.AppImage",
            execute=False,
        )


def test_open_path_rejects_directory(tmp_path: Path) -> None:
    registry_dir = tmp_path / ".appresolver" / "apps"
    directory = tmp_path / "Downloads"
    directory.mkdir()

    with pytest.raises(AppResolverError, match="not a regular file"):
        files.open_path(
            AppRegistry(registry_dir),
            StatePaths.from_registry_dir(registry_dir),
            directory,
            execute=False,
        )


def test_open_appimage_plan_only_mutates_nothing(tmp_path: Path) -> None:
    registry_dir = tmp_path / ".appresolver" / "apps"
    state_paths = StatePaths.from_registry_dir(registry_dir)
    source_path = write_file(tmp_path / "downloads" / "Example.AppImage")

    result = files.open_path(AppRegistry(registry_dir), state_paths, source_path, execute=False)

    assert result["detected_type"] == "appimage"
    assert result["supported"] is True
    assert result["status"] == "planned-import"
    assert result["executed"] is False
    assert result["route"] == "managed-appimage-import"
    assert not state_paths.apps_dir.exists()
    assert not state_paths.appimages_dir.exists()
    assert not state_paths.launchers_dir.exists()


def test_open_appimage_execute_imports_through_managed_appimage_backend(tmp_path: Path) -> None:
    registry_dir = tmp_path / ".appresolver" / "apps"
    state_paths = StatePaths.from_registry_dir(registry_dir)
    source_path = write_file(tmp_path / "downloads" / "Example.AppImage")

    result = files.open_path(AppRegistry(registry_dir), state_paths, source_path, execute=True)

    assert result["status"] == "imported"
    assert result["executed"] is True
    assert result["app_id"] == "Example"
    assert (state_paths.apps_dir / "Example.json").exists()
    assert (state_paths.appimages_dir / "Example.AppImage").exists()
    assert (state_paths.launchers_dir / "Example.desktop").exists()


def test_open_lowercase_appimage_execute_imports(tmp_path: Path) -> None:
    registry_dir = tmp_path / ".appresolver" / "apps"
    state_paths = StatePaths.from_registry_dir(registry_dir)
    source_path = write_file(tmp_path / "downloads" / "Example.appimage")

    result = files.open_path(AppRegistry(registry_dir), state_paths, source_path, execute=True)

    assert result["status"] == "imported"
    assert result["app_id"] == "Example"
    assert (state_paths.appimages_dir / "Example.AppImage").exists()


@pytest.mark.parametrize(
    ("filename", "route", "message"),
    [
        ("example.deb", "future-debian-environment", ".deb import is not implemented yet"),
        ("example.rpm", "future-rpm-environment", ".rpm import is not implemented yet"),
        ("setup.exe", "future-windows-compatibility", "Windows installer support is not implemented yet"),
    ],
)
def test_open_future_route_plan_only_is_non_mutating(
    tmp_path: Path, filename: str, route: str, message: str
) -> None:
    registry_dir = tmp_path / ".appresolver" / "apps"
    state_paths = StatePaths.from_registry_dir(registry_dir)
    source_path = write_file(tmp_path / "downloads" / filename)

    result = files.open_path(AppRegistry(registry_dir), state_paths, source_path, execute=False)

    assert result["supported"] is False
    assert result["status"] == "unsupported"
    assert result["route"] == route
    assert message in str(result["message"])
    assert result["actions"] == []
    assert not state_paths.state_root.exists()


@pytest.mark.parametrize(
    ("filename", "error"),
    [
        ("example.flatpakref", "Flatpak ref execution is not implemented yet"),
        ("example.deb", ".deb import is not implemented yet"),
        ("example.rpm", ".rpm import is not implemented yet"),
        ("setup.exe", "Windows installer support is not implemented yet"),
        ("install.sh", "shell scripts are unsafe"),
        ("unknown.bin", "unsupported file type"),
    ],
)
def test_open_unsupported_execute_fails_clearly(tmp_path: Path, filename: str, error: str) -> None:
    registry_dir = tmp_path / ".appresolver" / "apps"
    source_path = write_file(tmp_path / "downloads" / filename)

    with pytest.raises(AppResolverError, match=error):
        files.open_path(
            AppRegistry(registry_dir),
            StatePaths.from_registry_dir(registry_dir),
            source_path,
            execute=True,
        )
