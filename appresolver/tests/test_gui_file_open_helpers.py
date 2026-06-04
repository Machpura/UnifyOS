from __future__ import annotations

from pathlib import Path

import pytest

from appresolver.registry import AppRegistry
from appresolver.gui import file_open_helpers
from appresolver.state import StatePaths


def write_file(path: Path, content: str = "content") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def test_appimage_file_open_view_has_import_action_and_planned_actions(tmp_path: Path) -> None:
    registry_dir = tmp_path / ".appresolver" / "apps"
    state_paths = StatePaths.from_registry_dir(registry_dir)
    source_path = write_file(tmp_path / "downloads" / "Example.AppImage")

    result = file_open_helpers.plan_file_open(AppRegistry(registry_dir), state_paths, source_path)
    view = file_open_helpers.build_file_open_view(result)

    assert view["title"] == "Install Example.AppImage?"
    assert view["file_name"] == "Example.AppImage"
    assert view["type_label"] == "AppImage"
    assert view["method_label"] == "Managed AppImage import"
    assert view["detected_type"] == "appimage"
    assert view["route"] == "managed-appimage-import"
    assert view["supported"] is True
    assert view["supported_text"] == "yes"
    assert view["short_message"] == "App Resolver will import this file without running it during install."
    assert view["can_execute"] is True
    assert view["action_label"] == "Import"
    assert view["details_available"] is True
    assert view["details_collapsed"] is True
    assert "will not be executed" in "\n".join(view["safety_notes"])
    assert len(view["planned_actions"]) == 4
    assert "Copy AppImage" in view["planned_actions"][0]


@pytest.mark.parametrize(
    ("filename", "detected_type", "type_label", "short_message"),
    [
        (
            "example.deb",
            "deb",
            "Debian package",
            "Debian package import is not implemented yet. Future route: Debian/Ubuntu compatibility environment.",
        ),
        (
            "example.rpm",
            "rpm",
            "RPM package",
            "RPM package import is not implemented yet. Future route: Fedora/RPM compatibility environment.",
        ),
        (
            "setup.exe",
            "windows-installer",
            "Windows installer",
            "Windows installer support is not implemented yet. Future route: Windows compatibility/Wine environment.",
        ),
        (
            "example.flatpakref",
            "flatpakref",
            "Flatpak ref",
            "Flatpak ref support is not implemented yet.",
        ),
        (
            "install.sh",
            "shell-script",
            "Shell script",
            "Shell scripts are refused in normal mode and are Owner Mode-only future work.",
        ),
        ("unknown.bin", "unknown", "Unknown file", "Unsupported file type."),
    ],
)
def test_unsupported_file_open_view_has_no_execute_action(
    tmp_path: Path, filename: str, detected_type: str, type_label: str, short_message: str
) -> None:
    registry_dir = tmp_path / ".appresolver" / "apps"
    state_paths = StatePaths.from_registry_dir(registry_dir)
    source_path = write_file(tmp_path / "downloads" / filename)

    result = file_open_helpers.plan_file_open(AppRegistry(registry_dir), state_paths, source_path)
    view = file_open_helpers.build_file_open_view(result)

    assert view["detected_type"] == detected_type
    assert view["title"] == f"Open {filename}?"
    assert view["type_label"] == type_label
    assert view["supported"] is False
    assert view["supported_text"] == "no"
    assert view["can_execute"] is False
    assert view["action_label"] == ""
    assert view["short_message"] == short_message
    assert view["details_available"] is True
    assert view["planned_actions"] == []


def test_file_open_success_view_disables_import_and_shows_success() -> None:
    view = file_open_helpers.build_file_open_success_view(
        {
            "app_id": "Example",
            "actions": [
                {"id": "chmod-appimage", "path": "/state/appimages/Example.AppImage"},
                {"id": "write-manifest", "path": "/state/apps/Example.json"},
            ],
        }
    )

    assert view["title"] == "Example was imported successfully."
    assert view["success_message"] == "Example was imported successfully."
    assert view["app_id"] == "Example"
    assert view["can_execute"] is False
    assert view["action_label"] == ""
    assert view["close_available"] is True
    assert view["details_available"] is True


def test_execute_file_open_calls_existing_file_router(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    registry_dir = tmp_path / ".appresolver" / "apps"
    state_paths = StatePaths.from_registry_dir(registry_dir)
    source_path = tmp_path / "downloads" / "Example.AppImage"
    calls: list[tuple[AppRegistry, StatePaths, Path, bool]] = []

    def fake_open_path(registry: AppRegistry, state_paths_arg: StatePaths, path: Path, execute: bool) -> dict[str, object]:
        calls.append((registry, state_paths_arg, path, execute))
        return {"status": "imported", "executed": True}

    monkeypatch.setattr(file_open_helpers.files, "open_path", fake_open_path)

    result = file_open_helpers.execute_file_open(AppRegistry(registry_dir), state_paths, source_path)

    assert result == {"status": "imported", "executed": True}
    assert len(calls) == 1
    assert calls[0][2] == source_path
    assert calls[0][3] is True


def test_imported_app_details_extracts_app_id_paths() -> None:
    details = file_open_helpers.imported_app_details(
        {
            "app_id": "Example",
            "actions": [
                {"id": "chmod-appimage", "path": "/state/appimages/Example.AppImage"},
                {"id": "write-manifest", "path": "/state/apps/Example.json"},
            ],
        }
    )

    assert details == [
        "Imported app ID: Example",
        "Managed AppImage: /state/appimages/Example.AppImage",
        "Manifest: /state/apps/Example.json",
    ]
