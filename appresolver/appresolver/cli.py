from __future__ import annotations

import argparse
import json
import sys
from dataclasses import replace
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
from appresolver.backends.podman import (
    PackageInstallPlan,
    PodmanPlan,
    PlannedAction,
    execute_actions,
    execute_plan,
    inspect_environment_runtime,
    plan_destroy_environment,
    plan_environment,
    plan_install_package,
    plan_start_environment,
    plan_stop_environment,
)
from appresolver.environment import EnvironmentManifest
from appresolver.environment_registry import EnvironmentRegistry
from appresolver.errors import AppResolverError
from appresolver.manifest import AppManifest, utc_timestamp
from appresolver.registry import AppRegistry, default_registry_dir, validate_app_id
from appresolver.runtime_policy import EXECUTE, RuntimePolicy
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

    plan_environment_parser = subparsers.add_parser(
        "plan-environment", help="show planned Podman actions for a defined environment"
    )
    plan_environment_parser.add_argument("environment_id")
    plan_environment_parser.add_argument(
        "--json",
        dest="json_output",
        action="store_true",
        default=argparse.SUPPRESS,
        help="print structured JSON output",
    )

    create_environment_parser = subparsers.add_parser(
        "create-environment", help="create a defined container environment with Podman"
    )
    create_environment_parser.add_argument("environment_id")
    create_environment_parser.add_argument(
        "--execute",
        action="store_true",
        help="execute planned Podman actions",
    )
    create_environment_parser.add_argument(
        "--json",
        dest="json_output",
        action="store_true",
        default=argparse.SUPPRESS,
        help="print structured JSON output",
    )

    destroy_environment_parser = subparsers.add_parser(
        "destroy-environment", help="destroy a created container environment runtime with Podman"
    )
    destroy_environment_parser.add_argument("environment_id")
    destroy_environment_parser.add_argument(
        "--execute",
        action="store_true",
        help="execute planned Podman cleanup actions",
    )
    destroy_environment_parser.add_argument(
        "--json",
        dest="json_output",
        action="store_true",
        default=argparse.SUPPRESS,
        help="print structured JSON output",
    )

    start_environment_parser = subparsers.add_parser(
        "start-environment", help="start a created or stopped container environment runtime with Podman"
    )
    start_environment_parser.add_argument("environment_id")
    start_environment_parser.add_argument(
        "--execute",
        action="store_true",
        help="execute planned Podman start action",
    )
    start_environment_parser.add_argument(
        "--json",
        dest="json_output",
        action="store_true",
        default=argparse.SUPPRESS,
        help="print structured JSON output",
    )

    stop_environment_parser = subparsers.add_parser(
        "stop-environment", help="stop a running container environment runtime with Podman"
    )
    stop_environment_parser.add_argument("environment_id")
    stop_environment_parser.add_argument(
        "--execute",
        action="store_true",
        help="execute planned Podman stop action",
    )
    stop_environment_parser.add_argument(
        "--json",
        dest="json_output",
        action="store_true",
        default=argparse.SUPPRESS,
        help="print structured JSON output",
    )

    inspect_environment_parser = subparsers.add_parser(
        "inspect-environment", help="compare an environment manifest with Podman runtime state"
    )
    inspect_environment_parser.add_argument("environment_id")
    inspect_environment_parser.add_argument(
        "--json",
        dest="json_output",
        action="store_true",
        default=argparse.SUPPRESS,
        help="print structured JSON output",
    )

    reconcile_environment_parser = subparsers.add_parser(
        "reconcile-environment", help="repair environment manifest status from Podman runtime state"
    )
    reconcile_environment_parser.add_argument("environment_id")
    reconcile_environment_parser.add_argument(
        "--execute",
        action="store_true",
        help="update the manifest status to match inspected runtime state",
    )
    reconcile_environment_parser.add_argument(
        "--json",
        dest="json_output",
        action="store_true",
        default=argparse.SUPPRESS,
        help="print structured JSON output",
    )

    install_package_parser = subparsers.add_parser(
        "install-package", help="install a native package inside a managed environment"
    )
    install_package_parser.add_argument("environment_id")
    install_package_parser.add_argument("package_name")
    install_package_parser.add_argument(
        "--execute",
        action="store_true",
        help="execute planned Podman package install actions",
    )
    install_package_parser.add_argument(
        "--json",
        dest="json_output",
        action="store_true",
        default=argparse.SUPPRESS,
        help="print structured JSON output",
    )

    show_environment_packages_parser = subparsers.add_parser(
        "show-environment-packages", help="show packages installed through App Resolver in an environment"
    )
    show_environment_packages_parser.add_argument("environment_id")
    show_environment_packages_parser.add_argument(
        "--json",
        dest="json_output",
        action="store_true",
        default=argparse.SUPPRESS,
        help="print structured JSON output",
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
        if args.command == "plan-environment":
            return command_plan_environment(environment_registry, args.environment_id, args.json_output)
        if args.command == "create-environment":
            return command_create_environment(
                environment_registry,
                args.environment_id,
                args.execute,
                args.json_output,
            )
        if args.command == "destroy-environment":
            return command_destroy_environment(
                environment_registry,
                args.environment_id,
                args.execute,
                args.json_output,
            )
        if args.command == "start-environment":
            return command_start_environment(
                environment_registry,
                args.environment_id,
                args.execute,
                args.json_output,
            )
        if args.command == "stop-environment":
            return command_stop_environment(
                environment_registry,
                args.environment_id,
                args.execute,
                args.json_output,
            )
        if args.command == "inspect-environment":
            return command_inspect_environment(environment_registry, args.environment_id, args.json_output)
        if args.command == "reconcile-environment":
            return command_reconcile_environment(
                environment_registry,
                args.environment_id,
                args.execute,
                args.json_output,
            )
        if args.command == "install-package":
            return command_install_package(
                environment_registry,
                args.environment_id,
                args.package_name,
                args.execute,
                args.json_output,
            )
        if args.command == "show-environment-packages":
            return command_show_environment_packages(environment_registry, args.environment_id, args.json_output)
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


def command_plan_environment(
    environment_registry: EnvironmentRegistry, environment_id: str, as_json: bool
) -> int:
    manifest = environment_registry.load(environment_id)
    plan = plan_environment(manifest)
    if as_json:
        print_json(plan.to_dict())
        return 0

    print_plan(plan)
    return 0


def command_create_environment(
    environment_registry: EnvironmentRegistry,
    environment_id: str,
    execute: bool,
    as_json: bool,
) -> int:
    manifest = environment_registry.load(environment_id)
    plan = plan_environment(manifest)
    if not execute:
        if as_json:
            print_json(create_environment_result(plan, status="planned", executed=False))
            return 0

        print_plan(plan)
        print("Execution not performed. Re-run with --execute to create the environment.")
        return 0

    RuntimePolicy(mode=EXECUTE).require_runtime_mutation_allowed(f"create environment {manifest.environment_id}")
    if manifest.status == "created":
        raise AppResolverError(
            f"environment '{manifest.environment_id}' is already created; refusing to recreate managed container"
        )

    execute_plan(plan)
    created_manifest = replace(manifest, status="created")
    try:
        environment_registry.update(created_manifest)
    except AppResolverError as exc:
        raise AppResolverError(
            "environment container may exist but registry update failed "
            f"for '{manifest.environment_id}': {exc}"
        ) from exc

    if as_json:
        print_json(create_environment_result(plan, status="created", executed=True))
        return 0

    print(f"Created environment {manifest.environment_id}")
    print("Executed Podman actions:")
    for action in plan.actions:
        print(" ".join(action.command))
    print(f"Manifest: {environment_registry.path_for(manifest.environment_id)}")
    return 0


def command_destroy_environment(
    environment_registry: EnvironmentRegistry,
    environment_id: str,
    execute: bool,
    as_json: bool,
) -> int:
    manifest = environment_registry.load(environment_id)
    plan = plan_destroy_environment(manifest)
    if manifest.status == "running":
        raise AppResolverError(
            f"environment '{manifest.environment_id}' is running; stop the environment before destroying it"
        )
    if manifest.status not in {"created", "stopped"}:
        raise AppResolverError(
            f"environment '{manifest.environment_id}' status is '{manifest.status}'; "
            "destroy requires status 'created' or 'stopped'"
        )

    if not execute:
        if as_json:
            print_json(environment_runtime_result(plan, status="planned-destroy", executed=False))
            return 0

        print_plan(plan)
        print("Execution not performed. Re-run with --execute to destroy the environment runtime.")
        return 0

    RuntimePolicy(mode=EXECUTE).require_runtime_mutation_allowed(f"destroy environment {manifest.environment_id}")
    execute_plan(plan)
    cleared_tracked_packages = bool(manifest.installed_packages())
    defined_manifest = replace(manifest.without_installed_packages(), status="defined")
    try:
        environment_registry.update(defined_manifest)
    except AppResolverError as exc:
        raise AppResolverError(
            "environment container may have been removed but registry update failed "
            f"for '{manifest.environment_id}': {exc}"
        ) from exc

    if as_json:
        print_json(
            {
                **environment_runtime_result(plan, status="defined", executed=True),
                "cleared_tracked_packages": cleared_tracked_packages,
            }
        )
        return 0

    print(f"Destroyed environment runtime {manifest.environment_id}")
    if cleared_tracked_packages:
        print("Cleared runtime package tracking.")
    else:
        print("No runtime package tracking to clear.")
    print("Executed Podman actions:")
    for action in plan.actions:
        print(" ".join(action.command))
    print(f"Manifest: {environment_registry.path_for(manifest.environment_id)}")
    return 0


def command_start_environment(
    environment_registry: EnvironmentRegistry,
    environment_id: str,
    execute: bool,
    as_json: bool,
) -> int:
    manifest = environment_registry.load(environment_id)
    plan = plan_start_environment(manifest)
    if manifest.status not in {"created", "stopped"}:
        raise AppResolverError(
            f"environment '{manifest.environment_id}' status is '{manifest.status}'; "
            "start requires status 'created' or 'stopped'"
        )

    if not execute:
        if as_json:
            print_json(environment_runtime_result(plan, status="planned-start", executed=False))
            return 0

        print_plan(plan)
        print("Execution not performed. Re-run with --execute to start the environment runtime.")
        return 0

    RuntimePolicy(mode=EXECUTE).require_runtime_mutation_allowed(f"start environment {manifest.environment_id}")
    execute_plan(plan)
    running_manifest = replace(manifest, status="running")
    try:
        environment_registry.update(running_manifest)
    except AppResolverError as exc:
        raise AppResolverError(
            "environment runtime state may have changed but registry update failed "
            f"for '{manifest.environment_id}': {exc}"
        ) from exc

    if as_json:
        print_json(environment_runtime_result(plan, status="running", executed=True))
        return 0

    print(f"Started environment runtime {manifest.environment_id}")
    print("Executed Podman actions:")
    for action in plan.actions:
        print(" ".join(action.command))
    print(f"Manifest: {environment_registry.path_for(manifest.environment_id)}")
    return 0


def command_stop_environment(
    environment_registry: EnvironmentRegistry,
    environment_id: str,
    execute: bool,
    as_json: bool,
) -> int:
    manifest = environment_registry.load(environment_id)
    plan = plan_stop_environment(manifest)
    if manifest.status != "running":
        raise AppResolverError(
            f"environment '{manifest.environment_id}' status is '{manifest.status}'; stop requires status 'running'"
        )

    if not execute:
        if as_json:
            print_json(environment_runtime_result(plan, status="planned-stop", executed=False))
            return 0

        print_plan(plan)
        print("Execution not performed. Re-run with --execute to stop the environment runtime.")
        return 0

    RuntimePolicy(mode=EXECUTE).require_runtime_mutation_allowed(f"stop environment {manifest.environment_id}")
    execute_plan(plan)
    stopped_manifest = replace(manifest, status="stopped")
    try:
        environment_registry.update(stopped_manifest)
    except AppResolverError as exc:
        raise AppResolverError(
            "environment runtime state may have changed but registry update failed "
            f"for '{manifest.environment_id}': {exc}"
        ) from exc

    if as_json:
        print_json(environment_runtime_result(plan, status="stopped", executed=True))
        return 0

    print(f"Stopped environment runtime {manifest.environment_id}")
    print("Executed Podman actions:")
    for action in plan.actions:
        print(" ".join(action.command))
    print(f"Manifest: {environment_registry.path_for(manifest.environment_id)}")
    return 0


def command_inspect_environment(
    environment_registry: EnvironmentRegistry,
    environment_id: str,
    as_json: bool,
) -> int:
    manifest = environment_registry.load(environment_id)
    result = environment_inspection_result(manifest)

    if as_json:
        print_json(result)
        return 0

    print_environment_inspection(result)
    return 0


def command_reconcile_environment(
    environment_registry: EnvironmentRegistry,
    environment_id: str,
    execute: bool,
    as_json: bool,
) -> int:
    manifest = environment_registry.load(environment_id)
    result = environment_inspection_result(manifest)
    suggested_status = result["suggested_status"]
    if not isinstance(suggested_status, str):
        raise AppResolverError(
            f"cannot reconcile environment '{manifest.environment_id}' because runtime status is "
            f"'{result['runtime_status']}'"
        )

    if result["consistent"] is True:
        output = {**result, "executed": False}
        if as_json:
            print_json(output)
            return 0

        print_environment_inspection(result)
        print("No reconciliation needed.")
        return 0

    if not execute:
        output = {**result, "executed": False}
        if as_json:
            print_json(output)
            return 0

        print_environment_inspection(result)
        print(f"Proposed manifest status: {suggested_status}")
        print("Execution not performed. Re-run with --execute to update the manifest.")
        return 0

    RuntimePolicy(mode=EXECUTE).require_runtime_mutation_allowed(f"reconcile environment {manifest.environment_id}")
    previous_status = manifest.status
    if previous_status != suggested_status:
        reconciled_manifest = replace(manifest, status=suggested_status)
        try:
            environment_registry.update(reconciled_manifest)
        except AppResolverError as exc:
            raise AppResolverError(
                "environment runtime state was inspected but registry update failed "
                f"for '{manifest.environment_id}': {exc}"
            ) from exc

    output = {
        "environment_id": manifest.environment_id,
        "previous_status": previous_status,
        "runtime_status": result["runtime_status"],
        "new_status": suggested_status,
        "executed": True,
    }
    if as_json:
        print_json(output)
        return 0

    print(f"Reconciled environment {manifest.environment_id}: {previous_status} -> {suggested_status}")
    return 0


def command_install_package(
    environment_registry: EnvironmentRegistry,
    environment_id: str,
    package_name: str,
    execute: bool,
    as_json: bool,
) -> int:
    manifest = environment_registry.load(environment_id)
    plan = plan_install_package(manifest, package_name)

    if not execute:
        if as_json:
            print_json(package_install_result(plan, status="planned-install", executed=False))
            return 0

        print_package_install_plan(plan)
        print("Execution not performed. Re-run with --execute to install the package.")
        return 0

    RuntimePolicy(mode=EXECUTE).require_runtime_mutation_allowed(
        f"install package {plan.package} in environment {manifest.environment_id}"
    )
    executed_actions = execute_package_install_plan(environment_registry, manifest, plan)
    track_installed_package(environment_registry, manifest.environment_id, plan.package, plan.package_manager)

    if as_json:
        print_json(package_install_result(plan, status="installed", executed=True, tracked=True))
        return 0

    print(f"Installed and tracked package {plan.package} in environment {manifest.environment_id}")
    print("Executed Podman actions:")
    for action in executed_actions:
        print(" ".join(action.command))
    print(f"Manifest: {environment_registry.path_for(manifest.environment_id)}")
    return 0


def execute_package_install_plan(
    environment_registry: EnvironmentRegistry,
    manifest: EnvironmentManifest,
    plan: PackageInstallPlan,
) -> list[PlannedAction]:
    start_actions = [action for action in plan.actions if action.id == "start-container"]
    remaining_actions = [action for action in plan.actions if action.id != "start-container"]
    executed_actions: list[PlannedAction] = []

    if start_actions:
        execute_actions(start_actions)
        executed_actions.extend(start_actions)
        running_manifest = replace(manifest, status="running")
        try:
            environment_registry.update(running_manifest)
        except AppResolverError as exc:
            raise AppResolverError(
                "environment runtime may be running but registry update failed "
                f"for '{manifest.environment_id}': {exc}"
            ) from exc

    execute_actions(remaining_actions)
    executed_actions.extend(remaining_actions)
    return executed_actions


def track_installed_package(
    environment_registry: EnvironmentRegistry,
    environment_id: str,
    package_name: str,
    package_manager: str,
) -> None:
    manifest = environment_registry.load(environment_id)
    if any(package["name"] == package_name for package in manifest.installed_packages()):
        return

    tracked_manifest = manifest.with_installed_package(package_name, package_manager, utc_timestamp())
    try:
        environment_registry.update(tracked_manifest)
    except AppResolverError as exc:
        raise AppResolverError(
            "package may have been installed in the runtime but registry tracking failed "
            f"for '{environment_id}': {exc}"
        ) from exc


def command_show_environment_packages(
    environment_registry: EnvironmentRegistry,
    environment_id: str,
    as_json: bool,
) -> int:
    manifest = environment_registry.load(environment_id)
    packages = manifest.installed_packages()
    if as_json:
        print_json(packages)
        return 0

    if not packages:
        print("No resolver-tracked packages.")
        return 0

    for package in packages:
        print(f"{package['name']}\t{package['manager']}\t{package['installed_at']}")
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


def print_plan(plan: PodmanPlan) -> None:
    print(f"Planned Podman actions for {plan.environment_id}:")
    for action in plan.actions:
        print(" ".join(action.command))


def print_package_install_plan(plan: PackageInstallPlan) -> None:
    print(f"Planned Podman actions for {plan.environment_id}:")
    for action in plan.actions:
        print(" ".join(action.command))


def create_environment_result(plan: PodmanPlan, status: str, executed: bool) -> dict[str, Any]:
    return environment_runtime_result(plan, status, executed)


def environment_runtime_result(plan: PodmanPlan, status: str, executed: bool) -> dict[str, Any]:
    return {
        "environment_id": plan.environment_id,
        "backend": plan.backend,
        "status": status,
        "executed": executed,
        "actions": [action.to_dict() for action in plan.actions],
    }


def package_install_result(
    plan: PackageInstallPlan, status: str, executed: bool, tracked: bool | None = None
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "environment_id": plan.environment_id,
        "package": plan.package,
        "package_manager": plan.package_manager,
        "status": status,
        "executed": executed,
        "actions": [action.to_dict() for action in plan.actions],
    }
    if tracked is not None:
        result["tracked"] = tracked
    return result


def environment_inspection_result(manifest: EnvironmentManifest) -> dict[str, object]:
    inspection = inspect_environment_runtime(manifest)
    suggested_status = suggested_manifest_status(manifest.status, inspection.runtime_status)
    consistent = suggested_status == manifest.status
    return {
        "environment_id": manifest.environment_id,
        "manifest_status": manifest.status,
        "runtime_status": inspection.runtime_status,
        "consistent": consistent,
        "suggested_status": suggested_status,
    }


def suggested_manifest_status(manifest_status: str, runtime_status: str) -> str | None:
    if runtime_status == "running":
        return "running"
    if runtime_status == "stopped":
        return "stopped"
    if runtime_status == "missing":
        if manifest_status in {"created", "running", "stopped"}:
            return "defined"
        if manifest_status == "defined":
            return "defined"
    return None


def print_environment_inspection(result: dict[str, object]) -> None:
    print(f"Environment {result['environment_id']}:")
    print(f"Manifest status: {result['manifest_status']}")
    print(f"Runtime status: {result['runtime_status']}")
    print(f"Consistent: {str(result['consistent']).lower()}")
    if result["suggested_status"] is not None:
        print(f"Suggested status: {result['suggested_status']}")
    else:
        print("Suggested status: unknown")


def print_json(value: Any) -> None:
    print(json.dumps(value, indent=2, sort_keys=True))
