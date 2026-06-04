from __future__ import annotations

from pathlib import Path

import pytest

from appresolver.errors import BackendError
from appresolver.manifest import AppManifest
from appresolver.registry import AppRegistry
from appresolver.services import apps
from appresolver.state import StatePaths


def make_flatpak_manifest(app_id: str = "com.example.App") -> AppManifest:
    return AppManifest(
        app_id=app_id,
        name=app_id,
        backend="flatpak",
        source={"type": "flatpak", "remote": "flathub", "app_id": app_id},
        permissions={"flatpak": {"Context": {"shared": "network"}}},
        trust_tier="community",
        installed_at="2026-06-03T12:00:00+00:00",
    )


def make_appimage_manifest(registry_dir: Path, app_id: str = "Example") -> AppManifest:
    state_paths = StatePaths.from_registry_dir(registry_dir)
    return AppManifest(
        app_id=app_id,
        name=app_id,
        backend="appimage",
        source={
            "type": "appimage",
            "original_path": str(registry_dir.parent / "source" / f"{app_id}.AppImage"),
            "managed_path": str(state_paths.appimages_dir / f"{app_id}.AppImage"),
            "launcher_path": str(state_paths.launchers_dir / f"{app_id}.desktop"),
        },
        permissions={"appimage": {"sandboxed": False, "executed_during_import": False}},
        trust_tier="unverified",
        installed_at="2026-06-03T12:00:00+00:00",
    )


def test_list_app_summaries_empty_registry(tmp_path: Path) -> None:
    assert apps.list_app_summaries(AppRegistry(tmp_path / "apps")) == []


def test_appimage_app_summary_includes_gui_fields(tmp_path: Path) -> None:
    registry_dir = tmp_path / ".appresolver" / "apps"
    registry = AppRegistry(registry_dir)
    manifest = make_appimage_manifest(registry_dir)
    registry.save(manifest)

    summary = apps.list_app_summaries(registry)[0]

    assert summary["app_id"] == "Example"
    assert summary["backend"] == "appimage"
    assert summary["status"] == "installed"
    assert summary["trust_tier"] == "unverified"
    assert summary["manifest_path"] == str(registry.path_for("Example"))
    assert summary["source_details"]["managed_path"] == manifest.source["managed_path"]
    assert summary["source_details"]["launcher_path"] == manifest.source["launcher_path"]
    assert "sandboxed: False" in summary["permissions_summary"]


def test_flatpak_app_summary_includes_gui_fields(tmp_path: Path) -> None:
    registry = AppRegistry(tmp_path / "apps")
    registry.save(make_flatpak_manifest("com.example.App"))

    summary = apps.list_app_summaries(registry)[0]

    assert summary["app_id"] == "com.example.App"
    assert summary["backend"] == "flatpak"
    assert summary["status"] == "installed"
    assert summary["source_summary"] == "flathub: com.example.App"
    assert summary["source_details"] == {
        "type": "flatpak",
        "app_id": "com.example.App",
        "remote": "flathub",
    }
    assert summary["permissions_summary"] == "Context"


def test_uninstall_appimage_removes_files_and_manifest(tmp_path: Path) -> None:
    registry_dir = tmp_path / ".appresolver" / "apps"
    registry = AppRegistry(registry_dir)
    manifest = make_appimage_manifest(registry_dir)
    managed_path = Path(str(manifest.source["managed_path"]))
    launcher_path = Path(str(manifest.source["launcher_path"]))
    managed_path.parent.mkdir(parents=True)
    launcher_path.parent.mkdir(parents=True)
    managed_path.write_text("appimage", encoding="utf-8")
    launcher_path.write_text("launcher", encoding="utf-8")
    registry.save(manifest)

    result = apps.uninstall_app(registry, StatePaths.from_registry_dir(registry_dir), "Example")

    assert result["status"] == "removed"
    assert not registry.exists("Example")
    assert not managed_path.exists()
    assert not launcher_path.exists()


def test_uninstall_flatpak_calls_backend_and_deletes_manifest(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    registry = AppRegistry(tmp_path / "apps")
    registry.save(make_flatpak_manifest("com.example.App"))
    calls: list[str] = []
    monkeypatch.setattr(apps.flatpak, "uninstall_flatpak", lambda app_id: calls.append(app_id))

    apps.uninstall_app(registry, StatePaths.from_registry_dir(tmp_path / "apps"), "com.example.App")

    assert calls == ["com.example.App"]
    assert not registry.exists("com.example.App")


def test_uninstall_flatpak_failure_leaves_manifest(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    registry = AppRegistry(tmp_path / "apps")
    registry.save(make_flatpak_manifest("com.example.App"))

    def fail_uninstall(app_id: str) -> None:
        raise BackendError("flatpak blocked")

    monkeypatch.setattr(apps.flatpak, "uninstall_flatpak", fail_uninstall)

    with pytest.raises(BackendError, match="flatpak blocked"):
        apps.uninstall_app(registry, StatePaths.from_registry_dir(tmp_path / "apps"), "com.example.App")

    assert registry.exists("com.example.App")
