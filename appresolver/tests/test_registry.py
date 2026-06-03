from __future__ import annotations

from pathlib import Path

import pytest

from appresolver.errors import AppNotFoundError, InvalidAppIdError
from appresolver.manifest import AppManifest
from appresolver.registry import AppRegistry, default_registry_dir, filename_for_app_id


def make_manifest(app_id: str = "com.example.App") -> AppManifest:
    return AppManifest(
        app_id=app_id,
        name=app_id,
        backend="flatpak",
        source={"type": "flatpak", "remote": "flathub", "app_id": app_id},
        permissions={"flatpak": {}},
        trust_tier="community",
        installed_at="2026-06-03T12:00:00+00:00",
    )


def test_registry_saves_manifest_with_safe_filename(tmp_path: Path) -> None:
    registry = AppRegistry(tmp_path)
    manifest = make_manifest("com.example.App")

    registry.save(manifest)

    assert (tmp_path / "com.example.App.json").exists()


def test_registry_loads_saved_manifest(tmp_path: Path) -> None:
    registry = AppRegistry(tmp_path)
    manifest = make_manifest()
    registry.save(manifest)

    loaded = registry.load(manifest.app_id)

    assert loaded == manifest


def test_registry_lists_manifests_sorted_by_app_id(tmp_path: Path) -> None:
    registry = AppRegistry(tmp_path)
    registry.save(make_manifest("org.zed.Zed"))
    registry.save(make_manifest("com.discordapp.Discord"))
    registry.save(make_manifest("app.alpha"))

    app_ids = [manifest.app_id for manifest in registry.list()]

    assert app_ids == ["app.alpha", "com.discordapp.Discord", "org.zed.Zed"]


def test_registry_delete_removes_manifest(tmp_path: Path) -> None:
    registry = AppRegistry(tmp_path)
    manifest = make_manifest()
    registry.save(manifest)

    registry.delete(manifest.app_id)

    assert not registry.exists(manifest.app_id)


def test_registry_delete_missing_manifest_raises_clear_error(tmp_path: Path) -> None:
    registry = AppRegistry(tmp_path)

    with pytest.raises(AppNotFoundError, match="not managed"):
        registry.delete("com.example.Missing")


def test_registry_load_missing_manifest_raises_clear_error(tmp_path: Path) -> None:
    registry = AppRegistry(tmp_path)

    with pytest.raises(AppNotFoundError, match="not managed"):
        registry.load("com.example.Missing")


@pytest.mark.parametrize(
    "app_id",
    [
        "",
        "../x",
        "a/b",
        "a\\b",
        ".hidden",
        "-bad",
        "bad app",
        "bad$app",
    ],
)
def test_registry_rejects_unsafe_app_ids(tmp_path: Path, app_id: str) -> None:
    registry = AppRegistry(tmp_path)

    with pytest.raises(InvalidAppIdError):
        registry.path_for(app_id)


def test_filename_for_app_id_uses_allowlisted_id() -> None:
    assert filename_for_app_id("com.example_App-1") == "com.example_App-1.json"


def test_default_registry_dir_is_cwd_relative(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)

    assert default_registry_dir() == tmp_path / ".appresolver" / "apps"

