from __future__ import annotations

import re
import shutil
from pathlib import Path

from appresolver.errors import BackendError
from appresolver.manifest import AppManifest, utc_timestamp
from appresolver.registry import validate_app_id
from appresolver.state import StatePaths


UNSUPPORTED_APP_ID_CHARACTERS = re.compile(r"[^A-Za-z0-9._-]+")


def state_root_for_registry(registry_dir: Path) -> Path:
    return StatePaths.from_registry_dir(registry_dir).state_root


def resolve_state_root(registry_dir: Path) -> Path:
    return StatePaths.from_registry_dir(registry_dir).resolved_state_root()


def appimages_dir_for_registry(registry_dir: Path) -> Path:
    return StatePaths.from_registry_dir(registry_dir).appimages_dir


def launchers_dir_for_registry(registry_dir: Path) -> Path:
    return StatePaths.from_registry_dir(registry_dir).launchers_dir


def derive_app_id(source_path: Path) -> str:
    normalized = UNSUPPORTED_APP_ID_CHARACTERS.sub("-", source_path.stem)
    return validate_app_id(normalized)


def validate_source_path(source_path: Path) -> Path:
    if not source_path.exists():
        raise BackendError(f"AppImage source does not exist: {source_path}")
    if not source_path.is_file():
        raise BackendError(f"AppImage source is not a regular file: {source_path}")
    if source_path.suffix.lower() != ".appimage":
        raise BackendError(f"AppImage source must end with .AppImage: {source_path}")
    return source_path.resolve()


def managed_appimage_path(registry_dir: Path, app_id: str) -> Path:
    return managed_appimage_path_for_state(StatePaths.from_registry_dir(registry_dir), app_id)


def launcher_path(registry_dir: Path, app_id: str) -> Path:
    return launcher_path_for_state(StatePaths.from_registry_dir(registry_dir), app_id)


def managed_appimage_path_for_state(state_paths: StatePaths, app_id: str) -> Path:
    return state_paths.appimages_dir / f"{validate_app_id(app_id)}.AppImage"


def launcher_path_for_state(state_paths: StatePaths, app_id: str) -> Path:
    return state_paths.launchers_dir / f"{validate_app_id(app_id)}.desktop"


def import_appimage(source_path: Path, registry_dir: Path) -> AppManifest:
    return import_appimage_for_state(source_path, StatePaths.from_registry_dir(registry_dir))


def import_appimage_for_state(source_path: Path, state_paths: StatePaths) -> AppManifest:
    resolved_source = validate_source_path(source_path)
    app_id = derive_app_id(resolved_source)
    managed_path = managed_appimage_path_for_state(state_paths, app_id)
    desktop_path = launcher_path_for_state(state_paths, app_id)

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
        cleanup_import_artifacts_for_state(state_paths, managed_path, desktop_path)
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
            f"Exec={quote_desktop_exec_path(managed_path)}",
            "Terminal=false",
            "",
        ]
    )
    desktop_path.write_text(launcher, encoding="utf-8")


def quote_desktop_exec_path(path: Path) -> str:
    value = str(path)
    escaped = value.replace("\\", "\\\\").replace('"', '\\"').replace("$", "\\$").replace("`", "\\`")
    return f'"{escaped}"'


def uninstall_appimage(manifest: AppManifest, registry_dir: Path) -> None:
    uninstall_appimage_for_state(manifest, StatePaths.from_registry_dir(registry_dir))


def uninstall_appimage_for_state(manifest: AppManifest, state_paths: StatePaths) -> None:
    if manifest.backend != "appimage":
        raise BackendError(f"cannot uninstall non-AppImage manifest with AppImage backend: {manifest.backend}")

    managed_path = source_path_from_manifest(manifest, "managed_path")
    desktop_path = source_path_from_manifest(manifest, "launcher_path")
    resolved_managed_path = validate_managed_path(managed_path, state_paths)
    resolved_desktop_path = validate_managed_path(desktop_path, state_paths)
    remove_resolved_if_present(resolved_managed_path)
    remove_resolved_if_present(resolved_desktop_path)


def source_path_from_manifest(manifest: AppManifest, key: str) -> Path:
    value = manifest.source.get(key)
    if not isinstance(value, str) or not value:
        raise BackendError(f"AppImage manifest is missing source.{key}")
    return Path(value)


def cleanup_import_artifacts(registry_dir: Path, *paths: Path) -> None:
    cleanup_import_artifacts_for_state(StatePaths.from_registry_dir(registry_dir), *paths)


def cleanup_import_artifacts_for_state(state_paths: StatePaths, *paths: Path) -> None:
    for path in paths:
        try:
            remove_if_present(path, state_paths)
        except BackendError:
            continue


def remove_if_present(path: Path, state_paths: StatePaths) -> None:
    resolved_path = validate_managed_path(path, state_paths)
    remove_resolved_if_present(resolved_path)


def remove_resolved_if_present(resolved_path: Path) -> None:
    try:
        resolved_path.unlink()
    except FileNotFoundError:
        return
    except OSError as exc:
        raise BackendError(f"failed to remove managed AppImage file {resolved_path}: {exc}") from exc


def validate_managed_path(path: Path, state_paths: StatePaths) -> Path:
    try:
        return state_paths.validate_inside_state_root(path)
    except BackendError as exc:
        raise BackendError(f"managed AppImage path is outside resolver state: {path}") from exc


def resolve_managed_path(path: Path) -> Path:
    return path.resolve(strict=False)


def is_inside_state_root(path: Path, state_root: Path) -> bool:
    resolved_state_root = state_root.resolve(strict=False)
    return path == resolved_state_root or path.is_relative_to(resolved_state_root)
