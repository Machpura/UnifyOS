from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from appresolver.backends.podman import (
    PodmanPlan,
    execute_plan,
    inspect_environment_runtime,
    plan_destroy_environment,
    plan_environment,
    plan_start_environment,
    plan_stop_environment,
)
from appresolver.environment import EnvironmentManifest
from appresolver.environment_registry import EnvironmentRegistry
from appresolver.errors import AppResolverError
from appresolver.manifest import utc_timestamp
from appresolver.runtime_policy import EXECUTE, RuntimePolicy


@dataclass(frozen=True)
class RuntimeCommandResult:
    plan: PodmanPlan
    output: dict[str, Any]
    manifest_path: Path | None = None


def define_environment(
    environment_registry: EnvironmentRegistry,
    environment_id: str,
    name: str,
    backend: str,
    image: str,
    dry_run: bool,
) -> EnvironmentManifest:
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

    if not dry_run:
        environment_registry.save(manifest)
    return manifest


def list_environments(environment_registry: EnvironmentRegistry) -> list[EnvironmentManifest]:
    return environment_registry.list()


def load_environment(environment_registry: EnvironmentRegistry, environment_id: str) -> EnvironmentManifest:
    return environment_registry.load(environment_id)


def delete_environment(
    environment_registry: EnvironmentRegistry,
    environment_id: str,
    dry_run: bool,
) -> EnvironmentManifest:
    manifest = environment_registry.load(environment_id)
    if not dry_run:
        environment_registry.delete(manifest.environment_id)
    return manifest


def plan_environment_command(environment_registry: EnvironmentRegistry, environment_id: str) -> PodmanPlan:
    manifest = environment_registry.load(environment_id)
    return plan_environment(manifest)


def create_environment(
    environment_registry: EnvironmentRegistry,
    environment_id: str,
    execute: bool,
) -> RuntimeCommandResult:
    manifest = environment_registry.load(environment_id)
    plan = plan_environment(manifest)
    if not execute:
        return RuntimeCommandResult(plan=plan, output=environment_runtime_result(plan, "planned", False))

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

    return RuntimeCommandResult(
        plan=plan,
        output=environment_runtime_result(plan, "created", True),
        manifest_path=environment_registry.path_for(manifest.environment_id),
    )


def destroy_environment(
    environment_registry: EnvironmentRegistry,
    environment_id: str,
    execute: bool,
) -> RuntimeCommandResult:
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
        return RuntimeCommandResult(plan=plan, output=environment_runtime_result(plan, "planned-destroy", False))

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

    return RuntimeCommandResult(
        plan=plan,
        output={
            **environment_runtime_result(plan, "defined", True),
            "cleared_tracked_packages": cleared_tracked_packages,
        },
        manifest_path=environment_registry.path_for(manifest.environment_id),
    )


def start_environment(
    environment_registry: EnvironmentRegistry,
    environment_id: str,
    execute: bool,
) -> RuntimeCommandResult:
    manifest = environment_registry.load(environment_id)
    plan = plan_start_environment(manifest)
    if manifest.status not in {"created", "stopped"}:
        raise AppResolverError(
            f"environment '{manifest.environment_id}' status is '{manifest.status}'; "
            "start requires status 'created' or 'stopped'"
        )

    if not execute:
        return RuntimeCommandResult(plan=plan, output=environment_runtime_result(plan, "planned-start", False))

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

    return RuntimeCommandResult(
        plan=plan,
        output=environment_runtime_result(plan, "running", True),
        manifest_path=environment_registry.path_for(manifest.environment_id),
    )


def stop_environment(
    environment_registry: EnvironmentRegistry,
    environment_id: str,
    execute: bool,
) -> RuntimeCommandResult:
    manifest = environment_registry.load(environment_id)
    plan = plan_stop_environment(manifest)
    if manifest.status != "running":
        raise AppResolverError(
            f"environment '{manifest.environment_id}' status is '{manifest.status}'; stop requires status 'running'"
        )

    if not execute:
        return RuntimeCommandResult(plan=plan, output=environment_runtime_result(plan, "planned-stop", False))

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

    return RuntimeCommandResult(
        plan=plan,
        output=environment_runtime_result(plan, "stopped", True),
        manifest_path=environment_registry.path_for(manifest.environment_id),
    )


def inspect_environment(environment_registry: EnvironmentRegistry, environment_id: str) -> dict[str, object]:
    manifest = environment_registry.load(environment_id)
    return environment_inspection_result(manifest)


def reconcile_environment(
    environment_registry: EnvironmentRegistry,
    environment_id: str,
    execute: bool,
) -> dict[str, object]:
    manifest = environment_registry.load(environment_id)
    result = environment_inspection_result(manifest)
    suggested_status = result["suggested_status"]
    if not isinstance(suggested_status, str):
        raise AppResolverError(
            f"cannot reconcile environment '{manifest.environment_id}' because runtime status is "
            f"'{result['runtime_status']}'"
        )

    if result["consistent"] is True:
        return {**result, "executed": False}

    if not execute:
        return {**result, "executed": False}

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

    return {
        "environment_id": manifest.environment_id,
        "previous_status": previous_status,
        "runtime_status": result["runtime_status"],
        "new_status": suggested_status,
        "executed": True,
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


def environment_runtime_result(plan: PodmanPlan, status: str, executed: bool) -> dict[str, Any]:
    return {
        "environment_id": plan.environment_id,
        "backend": plan.backend,
        "status": status,
        "executed": executed,
        "actions": [action.to_dict() for action in plan.actions],
    }


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
