from __future__ import annotations

from appresolver.environment import EnvironmentManifest
from appresolver.errors import AppResolverError
from appresolver.services.environments import environment_inspection_result


def environment_summary_result(manifest: EnvironmentManifest) -> dict[str, object]:
    if manifest.backend != "container":
        raise AppResolverError(
            f"environment summary requires environment backend 'container', got '{manifest.backend}'"
        )

    inspection = environment_inspection_result(manifest)
    return {
        "environment_id": manifest.environment_id,
        "name": manifest.name,
        "image": manifest.image,
        "manifest_status": manifest.status,
        "runtime_status": inspection["runtime_status"],
        "consistent": inspection["consistent"],
        "suggested_status": inspection["suggested_status"],
        "tracked_packages": manifest.installed_packages(),
        "available_actions": available_environment_actions(
            manifest.status,
            str(inspection["runtime_status"]),
            bool(inspection["consistent"]),
        ),
    }


def available_environment_actions(
    manifest_status: str,
    runtime_status: str,
    consistent: bool,
) -> list[str]:
    if manifest_status == "defined" and runtime_status == "missing":
        return ["create-environment"]
    if manifest_status in {"created", "stopped"} and runtime_status == "stopped":
        return ["start-environment", "destroy-environment", "install-package", "remove-package"]
    if manifest_status == "running" and runtime_status == "running":
        return ["stop-environment", "install-package", "remove-package"]
    if not consistent:
        return ["reconcile-environment"]
    return []
