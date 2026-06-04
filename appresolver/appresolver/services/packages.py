from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from appresolver.backends.podman import (
    PackageInstallPlan,
    PackageRemovePlan,
    PlannedAction,
    execute_actions,
    plan_install_package,
    plan_remove_package,
)
from appresolver.environment import EnvironmentManifest, PackageRecord
from appresolver.environment_registry import EnvironmentRegistry
from appresolver.errors import AppResolverError
from appresolver.manifest import utc_timestamp
from appresolver.runtime_policy import EXECUTE, RuntimePolicy


@dataclass(frozen=True)
class PackageCommandResult:
    plan: PackageInstallPlan | PackageRemovePlan
    output: dict[str, Any]
    executed_actions: list[PlannedAction]
    manifest_path: Path | None = None


def install_package(
    environment_registry: EnvironmentRegistry,
    environment_id: str,
    package_name: str,
    execute: bool,
) -> PackageCommandResult:
    manifest = environment_registry.load(environment_id)
    plan = plan_install_package(manifest, package_name)

    if not execute:
        return PackageCommandResult(
            plan=plan,
            output=package_install_result(plan, status="planned-install", executed=False),
            executed_actions=[],
        )

    RuntimePolicy(mode=EXECUTE).require_runtime_mutation_allowed(
        f"install package {plan.package} in environment {manifest.environment_id}"
    )
    executed_actions = execute_package_install_plan(environment_registry, manifest, plan)
    track_installed_package(environment_registry, manifest.environment_id, plan.package, plan.package_manager)

    return PackageCommandResult(
        plan=plan,
        output=package_install_result(plan, status="installed", executed=True, tracked=True),
        executed_actions=executed_actions,
        manifest_path=environment_registry.path_for(manifest.environment_id),
    )


def remove_package(
    environment_registry: EnvironmentRegistry,
    environment_id: str,
    package_name: str,
    execute: bool,
) -> PackageCommandResult:
    manifest = environment_registry.load(environment_id)
    plan = plan_remove_package(manifest, package_name)

    if not execute:
        return PackageCommandResult(
            plan=plan,
            output=package_remove_result(plan, status="planned-remove", executed=False),
            executed_actions=[],
        )

    RuntimePolicy(mode=EXECUTE).require_runtime_mutation_allowed(
        f"remove package {plan.package} from environment {manifest.environment_id}"
    )
    executed_actions = execute_package_remove_plan(environment_registry, manifest, plan)
    untrack_installed_package(environment_registry, manifest.environment_id, plan.package)

    return PackageCommandResult(
        plan=plan,
        output=package_remove_result(plan, status="removed", executed=True, tracked=False),
        executed_actions=executed_actions,
        manifest_path=environment_registry.path_for(manifest.environment_id),
    )


def tracked_packages(environment_registry: EnvironmentRegistry, environment_id: str) -> list[PackageRecord]:
    manifest = environment_registry.load(environment_id)
    return manifest.installed_packages()


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


def execute_package_remove_plan(
    environment_registry: EnvironmentRegistry,
    manifest: EnvironmentManifest,
    plan: PackageRemovePlan,
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


def untrack_installed_package(
    environment_registry: EnvironmentRegistry,
    environment_id: str,
    package_name: str,
) -> None:
    manifest = environment_registry.load(environment_id)
    untracked_manifest = manifest.without_installed_package(package_name)
    try:
        environment_registry.update(untracked_manifest)
    except AppResolverError as exc:
        raise AppResolverError(
            "package may have been removed from the runtime but registry tracking failed "
            f"for '{environment_id}': {exc}"
        ) from exc


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


def package_remove_result(
    plan: PackageRemovePlan, status: str, executed: bool, tracked: bool | None = None
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
