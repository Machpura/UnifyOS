from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from appresolver.backends import flatpak
from appresolver.backends.appimage import uninstall_appimage_for_state
from appresolver.errors import AppResolverError
from appresolver.manifest import AppManifest
from appresolver.registry import AppRegistry
from appresolver.state import StatePaths


def list_apps(registry: AppRegistry) -> list[AppManifest]:
    return registry.list()


def app_display_summary(registry: AppRegistry, manifest: AppManifest) -> dict[str, Any]:
    manifest_path = registry.path_for(manifest.app_id)
    return {
        "app_id": manifest.app_id,
        "name": manifest.name,
        "backend": manifest.backend,
        "status": "installed",
        "trust_tier": manifest.trust_tier,
        "source_summary": source_summary(manifest),
        "permissions_summary": permissions_summary(manifest),
        "manifest_path": str(manifest_path),
        "source_details": source_details(manifest),
    }


def list_app_summaries(registry: AppRegistry) -> list[dict[str, Any]]:
    return [app_display_summary(registry, manifest) for manifest in list_apps(registry)]


def load_app_summary(registry: AppRegistry, app_id: str) -> dict[str, Any]:
    return app_display_summary(registry, registry.load(app_id))


def uninstall_app(registry: AppRegistry, state_paths: StatePaths, app_id: str) -> dict[str, Any]:
    manifest = registry.load(app_id)
    if manifest.backend == "flatpak":
        flatpak.uninstall_flatpak(app_id)
    elif manifest.backend == "appimage":
        uninstall_appimage_for_state(manifest, state_paths)
    else:
        raise AppResolverError(f"unsupported backend for uninstall in v0: {manifest.backend}")

    registry.delete(app_id)
    return {
        "status": "removed",
        "app_id": app_id,
        "backend": manifest.backend,
        "manifest_path": str(registry.path_for(app_id)),
    }


def source_summary(manifest: AppManifest) -> str:
    if manifest.backend == "appimage":
        managed_path = manifest.source.get("managed_path")
        if isinstance(managed_path, str) and managed_path:
            return f"Managed AppImage: {Path(managed_path).name}"
        return "Managed AppImage"
    if manifest.backend == "flatpak":
        app_id = manifest.source.get("app_id", manifest.app_id)
        remote = manifest.source.get("remote")
        if isinstance(remote, str) and remote:
            return f"{remote}: {app_id}"
        return str(app_id)
    source_type = manifest.source.get("type")
    return str(source_type) if source_type else "unknown"


def source_details(manifest: AppManifest) -> dict[str, str]:
    details: dict[str, str] = {}
    for key in ["type", "app_id", "remote", "original_path", "managed_path", "launcher_path"]:
        value = manifest.source.get(key)
        if isinstance(value, str) and value:
            details[key] = value
    return details


def permissions_summary(manifest: AppManifest) -> str:
    if not manifest.permissions:
        return "none"
    if manifest.backend == "appimage":
        appimage_permissions = manifest.permissions.get("appimage")
        if isinstance(appimage_permissions, dict):
            sandboxed = appimage_permissions.get("sandboxed")
            executed = appimage_permissions.get("executed_during_import")
            return f"sandboxed: {sandboxed}, executed during import: {executed}"
    if manifest.backend == "flatpak":
        flatpak_permissions = manifest.permissions.get("flatpak")
        if isinstance(flatpak_permissions, dict):
            sections = ", ".join(sorted(str(key) for key in flatpak_permissions))
            return sections or "none"
    return json.dumps(manifest.permissions, sort_keys=True)
