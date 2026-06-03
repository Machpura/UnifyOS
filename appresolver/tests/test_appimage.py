from __future__ import annotations

import os
import stat
from pathlib import Path
from typing import Any

import pytest

from appresolver.backends import appimage
from appresolver.backends.appimage import (
    derive_app_id,
    import_appimage,
    launcher_path,
    managed_appimage_path,
    uninstall_appimage,
    validate_source_path,
)
from appresolver.errors import BackendError
from appresolver.manifest import AppManifest
from appresolver.registry import AppRegistry


def write_appimage(path: Path, content: str = "#!/bin/sh\nexit 0\n") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def make_appimage_manifest(registry_dir: Path, app_id: str = "Example") -> AppManifest:
    return AppManifest(
        app_id=app_id,
        name=app_id,
        backend="appimage",
        source={
            "type": "appimage",
            "original_path": str(registry_dir.parent / "source" / f"{app_id}.AppImage"),
            "managed_path": str(managed_appimage_path(registry_dir, app_id)),
            "launcher_path": str(launcher_path(registry_dir, app_id)),
        },
        permissions={"appimage": {"sandboxed": False, "executed_during_import": False}},
        trust_tier="unverified",
        installed_at="2026-06-03T12:00:00+00:00",
    )


def test_import_appimage_copies_chmods_generates_launcher_and_manifest(tmp_path: Path) -> None:
    registry_dir = tmp_path / ".appresolver" / "apps"
    source_path = write_appimage(tmp_path / "downloads" / "Example.AppImage")

    manifest = import_appimage(source_path, registry_dir)

    managed_path = managed_appimage_path(registry_dir, "Example")
    desktop_path = launcher_path(registry_dir, "Example")
    assert managed_path.read_text(encoding="utf-8") == source_path.read_text(encoding="utf-8")
    assert managed_path.stat().st_mode & stat.S_IXUSR
    assert desktop_path.read_text(encoding="utf-8") == "\n".join(
        [
            "[Desktop Entry]",
            "Type=Application",
            "Name=Example",
            f'Exec="{managed_path}"',
            "Terminal=false",
            "",
        ]
    )
    assert manifest.app_id == "Example"
    assert manifest.backend == "appimage"
    assert manifest.source["managed_path"] == str(managed_path)
    assert manifest.source["launcher_path"] == str(desktop_path)
    assert manifest.permissions == {"appimage": {"sandboxed": False, "executed_during_import": False}}
    assert manifest.trust_tier == "unverified"


def test_import_appimage_does_not_execute_source(tmp_path: Path) -> None:
    registry_dir = tmp_path / ".appresolver" / "apps"
    marker_path = tmp_path / "executed"
    source_path = write_appimage(tmp_path / "downloads" / "Example.AppImage", f"#!/bin/sh\ntouch {marker_path}\n")

    import_appimage(source_path, registry_dir)

    assert not marker_path.exists()


def test_derive_app_id_normalizes_filename_characters() -> None:
    assert derive_app_id(Path("Example App_1.AppImage")) == "Example-App_1"


@pytest.mark.parametrize(
    "source_name",
    [
        "Example.appimage",
        "Example",
        "Example.txt",
    ],
)
def test_validate_source_path_rejects_non_appimage_suffix(tmp_path: Path, source_name: str) -> None:
    source_path = write_appimage(tmp_path / source_name)

    with pytest.raises(BackendError, match=".AppImage"):
        validate_source_path(source_path)


def test_validate_source_path_rejects_missing_source(tmp_path: Path) -> None:
    with pytest.raises(BackendError, match="does not exist"):
        validate_source_path(tmp_path / "Missing.AppImage")


def test_validate_source_path_rejects_directory_source(tmp_path: Path) -> None:
    source_path = tmp_path / "Directory.AppImage"
    source_path.mkdir()

    with pytest.raises(BackendError, match="not a regular file"):
        validate_source_path(source_path)


def test_import_appimage_rejects_existing_managed_file(tmp_path: Path) -> None:
    registry_dir = tmp_path / ".appresolver" / "apps"
    source_path = write_appimage(tmp_path / "downloads" / "Example.AppImage")
    managed_path = managed_appimage_path(registry_dir, "Example")
    managed_path.parent.mkdir(parents=True)
    managed_path.write_text("existing", encoding="utf-8")

    with pytest.raises(BackendError, match="already exists"):
        import_appimage(source_path, registry_dir)

    assert managed_path.read_text(encoding="utf-8") == "existing"


def test_uninstall_appimage_removes_managed_file_and_launcher(tmp_path: Path) -> None:
    registry_dir = tmp_path / ".appresolver" / "apps"
    source_path = write_appimage(tmp_path / "downloads" / "Example.AppImage")
    manifest = import_appimage(source_path, registry_dir)
    managed_path = Path(str(manifest.source["managed_path"]))
    desktop_path = Path(str(manifest.source["launcher_path"]))

    uninstall_appimage(manifest, registry_dir)

    assert not managed_path.exists()
    assert not desktop_path.exists()


def test_uninstall_appimage_tolerates_missing_managed_files(tmp_path: Path) -> None:
    registry_dir = tmp_path / ".appresolver" / "apps"
    manifest = make_appimage_manifest(registry_dir)

    uninstall_appimage(manifest, registry_dir)


def test_uninstall_appimage_failure_raises_before_manifest_delete_step(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    registry_dir = tmp_path / ".appresolver" / "apps"
    source_path = write_appimage(tmp_path / "downloads" / "Example.AppImage")
    manifest = import_appimage(source_path, registry_dir)
    desktop_path = Path(str(manifest.source["launcher_path"]))
    original_unlink = Path.unlink

    def failing_unlink(path: Path, *args: Any, **kwargs: Any) -> None:
        if path == desktop_path:
            raise OSError("blocked")
        original_unlink(path, *args, **kwargs)

    registry = AppRegistry(registry_dir)
    registry.save(manifest)
    monkeypatch.setattr(Path, "unlink", failing_unlink)

    with pytest.raises(BackendError, match="blocked"):
        uninstall_appimage(manifest, registry_dir)

    assert registry.exists(manifest.app_id)


def test_managed_appimage_has_execute_bit(tmp_path: Path) -> None:
    registry_dir = tmp_path / ".appresolver" / "apps"
    source_path = write_appimage(tmp_path / "downloads" / "Example.AppImage")

    manifest = import_appimage(source_path, registry_dir)

    assert os.access(Path(str(manifest.source["managed_path"])), os.X_OK)


def test_import_appimage_cleans_up_managed_file_when_chmod_fails(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    registry_dir = tmp_path / ".appresolver" / "apps"
    source_path = write_appimage(tmp_path / "downloads" / "Example.AppImage")
    managed_path = managed_appimage_path(registry_dir, "Example")

    def fail_make_executable(path: Path) -> None:
        raise OSError("chmod blocked")

    monkeypatch.setattr(appimage, "make_executable", fail_make_executable)

    with pytest.raises(BackendError, match="chmod blocked"):
        import_appimage(source_path, registry_dir)

    assert not managed_path.exists()
    assert not launcher_path(registry_dir, "Example").exists()


def test_import_appimage_cleans_up_files_when_launcher_write_fails(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    registry_dir = tmp_path / ".appresolver" / "apps"
    source_path = write_appimage(tmp_path / "downloads" / "Example.AppImage")
    managed_path = managed_appimage_path(registry_dir, "Example")
    desktop_path = launcher_path(registry_dir, "Example")

    def fail_write_launcher(app_id: str, managed_path_arg: Path, desktop_path_arg: Path) -> None:
        desktop_path_arg.write_text("partial", encoding="utf-8")
        raise OSError("launcher blocked")

    monkeypatch.setattr(appimage, "write_launcher", fail_write_launcher)

    with pytest.raises(BackendError, match="launcher blocked"):
        import_appimage(source_path, registry_dir)

    assert not managed_path.exists()
    assert not desktop_path.exists()


def test_import_appimage_failure_cleanup_is_best_effort(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    registry_dir = tmp_path / ".appresolver" / "apps"
    source_path = write_appimage(tmp_path / "downloads" / "Example.AppImage")

    def fail_make_executable(path: Path) -> None:
        raise OSError("chmod blocked")

    def fail_cleanup(path: Path, state_root: Path) -> None:
        raise BackendError("cleanup blocked")

    monkeypatch.setattr(appimage, "make_executable", fail_make_executable)
    monkeypatch.setattr(appimage, "remove_if_present", fail_cleanup)

    with pytest.raises(BackendError, match="chmod blocked"):
        import_appimage(source_path, registry_dir)


def test_import_appimage_with_spaces_quotes_launcher_exec_path(tmp_path: Path) -> None:
    registry_dir = tmp_path / "state root" / ".appresolver" / "apps"
    source_path = write_appimage(tmp_path / "download dir" / "Example App.AppImage")

    manifest = import_appimage(source_path, registry_dir)

    desktop_path = Path(str(manifest.source["launcher_path"]))
    managed_path = Path(str(manifest.source["managed_path"]))
    assert f'Exec="{managed_path}"' in desktop_path.read_text(encoding="utf-8")


def test_import_appimage_rejects_existing_launcher(tmp_path: Path) -> None:
    registry_dir = tmp_path / ".appresolver" / "apps"
    source_path = write_appimage(tmp_path / "downloads" / "Example.AppImage")
    desktop_path = launcher_path(registry_dir, "Example")
    desktop_path.parent.mkdir(parents=True)
    desktop_path.write_text("existing", encoding="utf-8")

    with pytest.raises(BackendError, match="already exists"):
        import_appimage(source_path, registry_dir)

    assert desktop_path.read_text(encoding="utf-8") == "existing"


def test_uninstall_appimage_rejects_outside_managed_path_and_keeps_files(tmp_path: Path) -> None:
    registry_dir = tmp_path / ".appresolver" / "apps"
    outside_path = tmp_path / "outside.AppImage"
    outside_path.write_text("outside", encoding="utf-8")
    manifest = make_appimage_manifest(registry_dir)
    manifest = AppManifest(
        app_id=manifest.app_id,
        name=manifest.name,
        backend=manifest.backend,
        source={**manifest.source, "managed_path": str(outside_path)},
        permissions=manifest.permissions,
        trust_tier=manifest.trust_tier,
        installed_at=manifest.installed_at,
    )

    with pytest.raises(BackendError, match="outside resolver state"):
        uninstall_appimage(manifest, registry_dir)

    assert outside_path.exists()


def test_uninstall_appimage_rejects_outside_launcher_path_before_deleting_managed_file(tmp_path: Path) -> None:
    registry_dir = tmp_path / ".appresolver" / "apps"
    manifest = make_appimage_manifest(registry_dir)
    managed_path = Path(str(manifest.source["managed_path"]))
    managed_path.parent.mkdir(parents=True)
    managed_path.write_text("managed", encoding="utf-8")
    outside_launcher = tmp_path / "outside.desktop"
    outside_launcher.write_text("outside", encoding="utf-8")
    manifest = AppManifest(
        app_id=manifest.app_id,
        name=manifest.name,
        backend=manifest.backend,
        source={**manifest.source, "launcher_path": str(outside_launcher)},
        permissions=manifest.permissions,
        trust_tier=manifest.trust_tier,
        installed_at=manifest.installed_at,
    )

    with pytest.raises(BackendError, match="outside resolver state"):
        uninstall_appimage(manifest, registry_dir)

    assert managed_path.exists()
    assert outside_launcher.exists()
