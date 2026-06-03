from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from appresolver.backends.appimage import (
    derive_app_id,
    import_appimage,
    launcher_path,
    managed_appimage_path,
    uninstall_appimage,
    validate_source_path,
)
from appresolver.backends.flatpak import install_flatpak, uninstall_flatpak
from appresolver.errors import AppResolverError
from appresolver.manifest import AppManifest
from appresolver.registry import AppRegistry, default_registry_dir, validate_app_id


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="appresolver", description="App Resolver v0 CLI prototype")
    parser.add_argument(
        "--registry-dir",
        type=Path,
        default=default_registry_dir(),
        help="registry directory; defaults to ./.appresolver/apps/ relative to the current working directory",
    )
    parser.add_argument(
        "--json",
        dest="json_output",
        action="store_true",
        help="print structured JSON output for commands that support it",
    )
    parser.add_argument(
        "--dry-run",
        dest="dry_run",
        action="store_true",
        help="print planned actions without changing state for commands that support it",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    install_parser = subparsers.add_parser("install-flatpak", help="install a Flatpak app by app ID")
    install_parser.add_argument("app_id")
    install_parser.add_argument(
        "--dry-run",
        dest="dry_run",
        action="store_true",
        default=argparse.SUPPRESS,
        help="print planned actions without changing state",
    )

    import_appimage_parser = subparsers.add_parser("import-appimage", help="import an AppImage into managed storage")
    import_appimage_parser.add_argument("path", type=Path)
    import_appimage_parser.add_argument(
        "--dry-run",
        dest="dry_run",
        action="store_true",
        default=argparse.SUPPRESS,
        help="print planned actions without changing state",
    )

    list_parser = subparsers.add_parser("list", help="list resolver-managed apps")
    list_parser.add_argument(
        "--json",
        dest="json_output",
        action="store_true",
        default=argparse.SUPPRESS,
        help="print structured JSON output",
    )

    permissions_parser = subparsers.add_parser("permissions", help="show permissions for a resolver-managed app")
    permissions_parser.add_argument("app_id")
    permissions_parser.add_argument(
        "--json",
        dest="json_output",
        action="store_true",
        default=argparse.SUPPRESS,
        help="print structured JSON output",
    )

    uninstall_parser = subparsers.add_parser("uninstall", help="uninstall a resolver-managed app")
    uninstall_parser.add_argument("app_id")
    uninstall_parser.add_argument(
        "--dry-run",
        dest="dry_run",
        action="store_true",
        default=argparse.SUPPRESS,
        help="print planned actions without changing state",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    registry = AppRegistry(args.registry_dir)

    try:
        if args.command == "install-flatpak":
            return command_install_flatpak(registry, args.app_id, args.dry_run)
        if args.command == "import-appimage":
            return command_import_appimage(registry, args.path, args.dry_run)
        if args.command == "list":
            return command_list(registry, args.json_output)
        if args.command == "permissions":
            return command_permissions(registry, args.app_id, args.json_output)
        if args.command == "uninstall":
            return command_uninstall(registry, args.app_id, args.dry_run)
    except AppResolverError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    parser.error(f"unknown command: {args.command}")
    return 2


def command_install_flatpak(registry: AppRegistry, app_id: str, dry_run: bool) -> int:
    validate_app_id(app_id)
    if dry_run:
        print(f"Would run: flatpak install -y flathub {app_id}")
        print(f"Would run: flatpak info --show-permissions {app_id}")
        print(f"Would write manifest: {registry.path_for(app_id)}")
        return 0

    manifest = install_flatpak(app_id)
    registry.save(manifest)
    print(f"Installed {app_id} via Flatpak")
    print(f"Manifest: {registry.path_for(app_id)}")
    return 0


def command_import_appimage(registry: AppRegistry, source_path: Path, dry_run: bool) -> int:
    resolved_source = validate_source_path(source_path)
    app_id = derive_app_id(resolved_source)
    if registry.exists(app_id):
        raise AppResolverError(f"app '{app_id}' is already managed by App Resolver")

    managed_path = managed_appimage_path(registry.registry_dir, app_id)
    desktop_path = launcher_path(registry.registry_dir, app_id)
    if dry_run:
        print(f"Would copy: {resolved_source} -> {managed_path}")
        print(f"Would chmod executable: {managed_path}")
        print(f"Would write launcher: {desktop_path}")
        print(f"Would write manifest: {registry.path_for(app_id)}")
        return 0

    manifest = import_appimage(resolved_source, registry.registry_dir)
    registry.save(manifest)
    print(f"Imported {app_id} as managed AppImage")
    print(f"Manifest: {registry.path_for(app_id)}")
    return 0


def command_list(registry: AppRegistry, as_json: bool) -> int:
    manifests = registry.list()
    if as_json:
        print_json([manifest_summary(manifest) for manifest in manifests])
        return 0

    if not manifests:
        print("No resolver-managed apps.")
        return 0

    for manifest in manifests:
        print(f"{manifest.app_id}\t{manifest.backend}\t{manifest.trust_tier}")
    return 0


def command_permissions(registry: AppRegistry, app_id: str, as_json: bool) -> int:
    manifest = registry.load(app_id)
    if as_json:
        print_json({"app_id": manifest.app_id, "permissions": manifest.permissions})
        return 0

    print(f"Permissions for {manifest.app_id}:")
    print(json.dumps(manifest.permissions, indent=2, sort_keys=True))
    return 0


def command_uninstall(registry: AppRegistry, app_id: str, dry_run: bool) -> int:
    validate_app_id(app_id)
    manifest = registry.load(app_id)

    if dry_run:
        print_uninstall_plan(registry, manifest)
        return 0

    if manifest.backend == "flatpak":
        uninstall_flatpak(app_id)
    elif manifest.backend == "appimage":
        uninstall_appimage(manifest)
    else:
        raise AppResolverError(f"unsupported backend for uninstall in v0: {manifest.backend}")

    registry.delete(app_id)
    print(f"Uninstalled {app_id}")
    return 0


def print_uninstall_plan(registry: AppRegistry, manifest: AppManifest) -> None:
    if manifest.backend == "flatpak":
        print(f"Would run: flatpak uninstall -y {manifest.app_id}")
    elif manifest.backend == "appimage":
        managed_path = manifest.source.get("managed_path")
        desktop_path = manifest.source.get("launcher_path")
        print(f"Would remove managed AppImage: {managed_path}")
        print(f"Would remove launcher: {desktop_path}")
    else:
        raise AppResolverError(f"unsupported backend for uninstall in v0: {manifest.backend}")
    print(f"Would delete manifest: {registry.path_for(manifest.app_id)}")


def manifest_summary(manifest: AppManifest) -> dict[str, object]:
    return {
        "app_id": manifest.app_id,
        "name": manifest.name,
        "backend": manifest.backend,
        "trust_tier": manifest.trust_tier,
        "installed_at": manifest.installed_at,
        "source": manifest.source,
    }


def print_json(value: Any) -> None:
    print(json.dumps(value, indent=2, sort_keys=True))
