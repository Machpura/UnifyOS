from __future__ import annotations

from pathlib import Path
from typing import Any

from appresolver.backends.appimage import (
    cleanup_import_artifacts_for_state,
    derive_app_id,
    import_appimage_for_state,
    launcher_path_for_state,
    managed_appimage_path_for_state,
)
from appresolver.errors import AppResolverError
from appresolver.registry import AppRegistry
from appresolver.state import StatePaths


APPIMAGE_MESSAGE = "AppImage can be imported into resolver-managed state."
FLATPAKREF_MESSAGE = "Flatpak ref execution is not implemented yet."
DEB_MESSAGE = ".deb import is not implemented yet. Future route: Debian/Ubuntu compatibility environment."
RPM_MESSAGE = ".rpm import is not implemented yet. Future route: Fedora/RPM compatibility environment."
EXE_MESSAGE = "Windows installer support is not implemented yet. Future route: Windows compatibility/Wine environment."
SHELL_MESSAGE = "Shell scripts are unsafe in normal mode and are Owner Mode-only future work."
UNKNOWN_MESSAGE = "Unsupported file type."


def open_path(registry: AppRegistry, state_paths: StatePaths, path: Path, execute: bool) -> dict[str, Any]:
    resolved_path = validate_open_path(path)
    result = plan_open_path(registry, state_paths, resolved_path)
    if not execute:
        return result

    detected_type = str(result["detected_type"])
    if detected_type == "appimage":
        return execute_appimage_import(registry, state_paths, resolved_path, result)
    if detected_type == "flatpakref":
        raise AppResolverError("Flatpak ref execution is not implemented yet")
    if detected_type == "deb":
        raise AppResolverError(".deb import is not implemented yet")
    if detected_type == "rpm":
        raise AppResolverError(".rpm import is not implemented yet")
    if detected_type == "windows-installer":
        raise AppResolverError("Windows installer support is not implemented yet")
    if detected_type == "shell-script":
        raise AppResolverError("shell scripts are unsafe in normal mode and are Owner Mode-only future work")
    raise AppResolverError("unsupported file type")


def validate_open_path(path: Path) -> Path:
    if not path.exists():
        raise AppResolverError(f"file does not exist: {path}")
    if not path.is_file():
        raise AppResolverError(f"path is not a regular file: {path}")
    return path.resolve()


def plan_open_path(registry: AppRegistry, state_paths: StatePaths, path: Path) -> dict[str, Any]:
    detected_type = detect_file_type(path)
    if detected_type == "appimage":
        return appimage_plan(registry, state_paths, path)
    if detected_type == "flatpakref":
        return unsupported_plan(path, "flatpakref", "future-flatpakref-install", FLATPAKREF_MESSAGE)
    if detected_type == "deb":
        return unsupported_plan(path, "deb", "future-debian-environment", DEB_MESSAGE)
    if detected_type == "rpm":
        return unsupported_plan(path, "rpm", "future-rpm-environment", RPM_MESSAGE)
    if detected_type == "windows-installer":
        return unsupported_plan(path, "windows-installer", "future-windows-compatibility", EXE_MESSAGE)
    if detected_type == "shell-script":
        return unsupported_plan(path, "shell-script", "owner-mode-only", SHELL_MESSAGE)
    return unsupported_plan(path, "unknown", "unsupported", UNKNOWN_MESSAGE)


def detect_file_type(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".appimage":
        return "appimage"
    if suffix == ".flatpakref":
        return "flatpakref"
    if suffix == ".deb":
        return "deb"
    if suffix == ".rpm":
        return "rpm"
    if suffix == ".exe":
        return "windows-installer"
    if suffix == ".sh":
        return "shell-script"
    return "unknown"


def appimage_plan(registry: AppRegistry, state_paths: StatePaths, path: Path) -> dict[str, Any]:
    app_id = derive_app_id(path)
    managed_path = managed_appimage_path_for_state(state_paths, app_id)
    launcher_path = launcher_path_for_state(state_paths, app_id)
    return {
        "path": str(path),
        "detected_type": "appimage",
        "supported": True,
        "status": "planned-import",
        "executed": False,
        "route": "managed-appimage-import",
        "message": APPIMAGE_MESSAGE,
        "actions": [
            {
                "id": "copy-appimage",
                "description": "Copy AppImage into resolver-managed storage",
                "source": str(path),
                "target": str(managed_path),
            },
            {
                "id": "chmod-appimage",
                "description": "Mark managed AppImage executable",
                "path": str(managed_path),
            },
            {
                "id": "write-launcher",
                "description": "Write resolver-local launcher",
                "path": str(launcher_path),
            },
            {
                "id": "write-manifest",
                "description": "Write resolver app manifest",
                "path": str(registry.path_for(app_id)),
            },
        ],
    }


def execute_appimage_import(
    registry: AppRegistry,
    state_paths: StatePaths,
    path: Path,
    plan: dict[str, Any],
) -> dict[str, Any]:
    app_id = derive_app_id(path)
    if registry.exists(app_id):
        raise AppResolverError(f"app '{app_id}' is already managed by App Resolver")

    manifest = import_appimage_for_state(path, state_paths)
    try:
        registry.save(manifest)
    except AppResolverError:
        cleanup_import_artifacts_for_state(
            state_paths,
            Path(str(manifest.source["managed_path"])),
            Path(str(manifest.source["launcher_path"])),
            registry.path_for(manifest.app_id),
        )
        raise

    return {
        **plan,
        "status": "imported",
        "executed": True,
        "app_id": manifest.app_id,
    }


def unsupported_plan(path: Path, detected_type: str, route: str, message: str) -> dict[str, Any]:
    return {
        "path": str(path),
        "detected_type": detected_type,
        "supported": False,
        "status": "unsupported",
        "executed": False,
        "route": route,
        "message": message,
        "actions": [],
    }
