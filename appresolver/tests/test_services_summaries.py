from __future__ import annotations

import pytest

from appresolver.services.summaries import available_environment_actions


@pytest.mark.parametrize(
    ("manifest_status", "runtime_status", "consistent", "actions"),
    [
        ("defined", "missing", True, ["create-environment"]),
        (
            "created",
            "stopped",
            False,
            ["start-environment", "destroy-environment", "install-package", "remove-package"],
        ),
        (
            "stopped",
            "stopped",
            True,
            ["start-environment", "destroy-environment", "install-package", "remove-package"],
        ),
        ("running", "running", True, ["stop-environment", "install-package", "remove-package"]),
        ("created", "missing", False, ["reconcile-environment"]),
        ("defined", "unknown", False, ["reconcile-environment"]),
        ("defined", "unknown", True, []),
    ],
)
def test_available_environment_actions(
    manifest_status: str,
    runtime_status: str,
    consistent: bool,
    actions: list[str],
) -> None:
    assert available_environment_actions(manifest_status, runtime_status, consistent) == actions
