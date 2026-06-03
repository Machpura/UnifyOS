from __future__ import annotations

import re
import shutil
from pathlib import Path

from appresolver.errors import BackendError
from appresolver.manifest import AppManifest, utc_timestamp
from appresolver.registry import validate_app_id


UNSUPPORTED_APP_ID_CHARACTERS = re.compile(r"[^A-Za-z0-9._-]+")


def state_root_for_registry(registry_dir: Path) -> Path:
    return registry_dir.parent


def appimages_dir_for_registry(registry_dir: Path) -> Path:
    return state_root_for_registry(registry_dir) / "appimages"


def launchers_dir_for_registry(registry_dir: Path) -> Path:
    return state_root_for_registry(registry_dir) / "launchers"


def derive_app_id(source_path: Path) -> str:
    normalized = UNSUPPORTED_APP_ID_CHARACTERS.sub("-", source_path.stem)
    return validate_app_id(normalized)


def validate_source_path(source_path: Path) -> Path:
    if not source_path.exists():
        raise BackendError(f"AppImage source does not exist: {source_path}")
    if not source_path.is_file():
        raise BackendError(f"AppImage source is not a regular file: {source_path}")
    if source_path.suffix != ".AppImage":
        raise BackendError(f"AppImage source must end with .AppImage: {source_path}")
    return source_path.resolve()


def managed_appimage_path(registry_dir: Path, app_id: str) -> Path:
    return appimages_dir_for_registry(registry_dir) / f"{validate_app_id(app_id)}.AppImage"


def launcher_path(registry_dir: Path, app_id: str) -> Path:
    return launchers_dir_for_registry(registry_dir) / f"{validate_app_id(app_id)}.desktop"


def import_appimage(source_path: Path, registry_dir: Path) -> AppManifest:
    resolved_source = validate_source_path(source_path)
    app_id = derive_app_id(resolved_source)
    managed_path = managed_appimage_path(registry_dir, app_id)
    desktop_path = launcher_path(registry_dir, app_id)

    if managed_path.exists():
        raise BackendError(f"managed AppImage already exists: {managed_path}")
    if desktop_path.exists():
        raise BackendError(f"managed launcher already exists: {desktop_path}")

    try:
        managed_path.parent.mkdir(parents=True, exist_ok=True)
        desktop_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(resolved_source, managed_path)
        make_executable(managed_path)
        write_launcher(app_id, managed_path, desktop_path)
    except OSError as exc:
        raise BackendError(f"failed to import AppImage {resolved_source}: {exc}") from exc

    return AppManifest(
        app_id=app_id,
        name=app_id,
        backend="appimage",
        source={
            "type": "appimage",
            "original_path": str(resolved_source),
            "managed_path": str(managed_path),
            "launcher_path": str(desktop_path),
        },
        permissions={
            "appimage": {
                "sandboxed": False,
                "executed_during_import": False,
            }
        },
        trust_tier="unverified",
        installed_at=utc_timestamp(),
    )


def make_executable(path: Path) -> None:
    path.chmod(path.stat().st_mode | 0o111)


def write_launcher(app_id: str, managed_path: Path, desktop_path: Path) -> None:
    launcher = "\n".join(
        [
            "[Desktop Entry]",
            "Type=Application",
            f"Name={app_id}",
            f"Exec={managed_path}",
            "Terminal=false",
            "",
        ]
    )
    desktop_path.write_text(launcher, encoding="utf-8")


def uninstall_appimage(manifest: AppManifest) -> None:
    if manifest.backend != "appimage":
        raise BackendError(f"cannot uninstall non-AppImage manifest with AppImage backend: {manifest.backend}")

    managed_path = source_path_from_manifest(manifest, "managed_path")
    desktop_path = source_path_from_manifest(manifest, "launcher_path")
    remove_if_present(managed_path)
    remove_if_present(desktop_path)


def source_path_from_manifest(manifest: AppManifest, key: str) -> Path:
    value = manifest.source.get(key)
    if not isinstance(value, str) or not value:
        raise BackendError(f"AppImage manifest is missing source.{key}")
    return Path(value)


def remove_if_present(path: Path) -> None:
    try:
        path.unlink()
    except FileNotFoundError:
        return
    except OSError as exc:
        raise BackendError(f"failed to remove managed AppImage file {path}: {exc}") from exc

