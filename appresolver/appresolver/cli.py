from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from appresolver.backends.appimage import (
    cleanup_import_artifacts_for_state,
    derive_app_id,
    import_appimage_for_state,
    launcher_path_for_state,
    managed_appimage_path_for_state,
    uninstall_appimage_for_state,
    validate_source_path,
)
from appresolver.backends.flatpak import install_flatpak, uninstall_flatpak
from appresolver.environment import EnvironmentManifest
from appresolver.environment_registry import EnvironmentRegistry
from appresolver.errors import AppResolverError
from appresolver.manifest import AppManifest, utc_timestamp
from appresolver.registry import AppRegistry, default_registry_dir, validate_app_id
from appresolver.state import StatePaths


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

    define_environment_parser = subparsers.add_parser(
        "define-environment", help="define an environment without creating runtime resources"
    )
    define_environment_parser.add_argument("environment_id")
    define_environment_parser.add_argument("--name", required=True)
    define_environment_parser.add_argument("--backend", required=True)
    define_environment_parser.add_argument("--image", required=True)
    define_environment_parser.add_argument(
        "--dry-run",
        dest="dry_run",
        action="store_true",
        default=argparse.SUPPRESS,
        help="print planned actions without changing state",
    )

    list_environments_parser = subparsers.add_parser("list-environments", help="list defined environments")
    list_environments_parser.add_argument(
        "--json",
        dest="json_output",
        action="store_true",
        default=argparse.SUPPRESS,
        help="print structured JSON output",
    )

    show_environment_parser = subparsers.add_parser("show-environment", help="show one defined environment")
    show_environment_parser.add_argument("environment_id")
    show_environment_parser.add_argument(
        "--json",
        dest="json_output",
        action="store_true",
        default=argparse.SUPPRESS,
        help="print structured JSON output",
    )

    delete_environment_parser = subparsers.add_parser("delete-environment", help="delete an environment definition")
    delete_environment_parser.add_argument("environment_id")
    delete_environment_parser.add_argument(
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
    state_paths = StatePaths.from_registry_dir(args.registry_dir)
    environment_registry = EnvironmentRegistry(state_paths.environments_dir)

    try:
        if args.command == "install-flatpak":
            return command_install_flatpak(registry, args.app_id, args.dry_run)
        if args.command == "import-appimage":
            return command_import_appimage(registry, state_paths, args.path, args.dry_run)
        if args.command == "define-environment":
            return command_define_environment(
                environment_registry,
                args.environment_id,
                args.name,
                args.backend,
                args.image,
                args.dry_run,
            )
        if args.command == "list-environments":
            return command_list_environments(environment_registry, args.json_output)
        if args.command == "show-environment":
            return command_show_environment(environment_registry, args.environment_id, args.json_output)
        if args.command == "delete-environment":
            return command_delete_environment(environment_registry, args.environment_id, args.dry_run)
        if args.command == "list":
            return command_list(registry, args.json_output)
        if args.command == "permissions":
            return command_permissions(registry, args.app_id, args.json_output)
        if args.command == "uninstall":
            return command_uninstall(registry, state_paths, args.app_id, args.dry_run)
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


def command_define_environment(
    environment_registry: EnvironmentRegistry,
    environment_id: str,
    name: str,
    backend: str,
    image: str,
    dry_run: bool,
) -> int:
    manifest = EnvironmentManifest(
        environment_id=environment_id,
        name=name,
        backend=backend,
        image=image,
        status="defined",
        created_at=utc_timestamp(),
        permissions={},
        apps=[],
        source={"type": "manual"},
    )
    if environment_registry.exists(manifest.environment_id):
        raise AppResolverError(f"environment '{manifest.environment_id}' is already managed by App Resolver")

    if dry_run:
        print(f"Would write environment manifest: {environment_registry.path_for(manifest.environment_id)}")
        return 0

    environment_registry.save(manifest)
    print(f"Defined environment {manifest.environment_id}")
    print(f"Manifest: {environment_registry.path_for(manifest.environment_id)}")
    return 0


def command_list_environments(environment_registry: EnvironmentRegistry, as_json: bool) -> int:
    manifests = environment_registry.list()
    if as_json:
        print_json([environment_summary(manifest) for manifest in manifests])
        return 0

    if not manifests:
        print("No resolver-managed environments.")
        return 0

    for manifest in manifests:
        print(f"{manifest.environment_id}\t{manifest.backend}\t{manifest.status}")
    return 0


def command_show_environment(
    environment_registry: EnvironmentRegistry, environment_id: str, as_json: bool
) -> int:
    manifest = environment_registry.load(environment_id)
    if as_json:
        print_json(manifest.to_dict())
        return 0

    print(f"Environment {manifest.environment_id}:")
    print(json.dumps(manifest.to_dict(), indent=2, sort_keys=True))
    return 0


def command_delete_environment(
    environment_registry: EnvironmentRegistry, environment_id: str, dry_run: bool
) -> int:
    manifest = environment_registry.load(environment_id)
    if dry_run:
        print(f"Would delete environment manifest: {environment_registry.path_for(manifest.environment_id)}")
        return 0

    environment_registry.delete(manifest.environment_id)
    print(f"Deleted environment {manifest.environment_id}")
    return 0


def command_import_appimage(registry: AppRegistry, state_paths: StatePaths, source_path: Path, dry_run: bool) -> int:
    resolved_source = validate_source_path(source_path)
    app_id = derive_app_id(resolved_source)
    if registry.exists(app_id):
        raise AppResolverError(f"app '{app_id}' is already managed by App Resolver")

    managed_path = managed_appimage_path_for_state(state_paths, app_id)
    desktop_path = launcher_path_for_state(state_paths, app_id)
    if dry_run:
        print(f"Would copy: {resolved_source} -> {managed_path}")
        print(f"Would chmod executable: {managed_path}")
        print(f"Would write launcher: {desktop_path}")
        print(f"Would write manifest: {registry.path_for(app_id)}")
        return 0

    manifest = import_appimage_for_state(resolved_source, state_paths)
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


def command_uninstall(registry: AppRegistry, state_paths: StatePaths, app_id: str, dry_run: bool) -> int:
    validate_app_id(app_id)
    manifest = registry.load(app_id)

    if dry_run:
        print_uninstall_plan(registry, manifest)
        return 0

    if manifest.backend == "flatpak":
        uninstall_flatpak(app_id)
    elif manifest.backend == "appimage":
        uninstall_appimage_for_state(manifest, state_paths)
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


def environment_summary(manifest: EnvironmentManifest) -> dict[str, object]:
    return {
        "environment_id": manifest.environment_id,
        "name": manifest.name,
        "backend": manifest.backend,
        "image": manifest.image,
        "status": manifest.status,
        "created_at": manifest.created_at,
    }


def print_json(value: Any) -> None:
    print(json.dumps(value, indent=2, sort_keys=True))
