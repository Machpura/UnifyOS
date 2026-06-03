from __future__ import annotations

import pytest

from appresolver.errors import RuntimeActionBlocked
from appresolver.runtime_policy import (
    EXECUTE,
    PLAN_ONLY,
    RuntimePolicy,
    default_runtime_policy,
    ensure_runtime_mutation_allowed,
)


def test_runtime_policy_defaults_to_plan_only() -> None:
    policy = RuntimePolicy()

    assert policy.mode == PLAN_ONLY
    assert not policy.allows_runtime_mutation()


def test_default_runtime_policy_is_plan_only() -> None:
    policy = default_runtime_policy()

    assert policy.mode == PLAN_ONLY
    assert not policy.allows_runtime_mutation()


def test_plan_only_blocks_runtime_mutation() -> None:
    policy = RuntimePolicy()

    with pytest.raises(RuntimeActionBlocked, match="podman create.*plan-only"):
        policy.require_runtime_mutation_allowed("podman create")


def test_plan_only_helper_blocks_runtime_mutation() -> None:
    with pytest.raises(RuntimeActionBlocked, match="podman create.*plan-only"):
        ensure_runtime_mutation_allowed(RuntimePolicy(), "podman create")


def test_execute_mode_allows_runtime_mutation() -> None:
    policy = RuntimePolicy(mode=EXECUTE)

    assert policy.allows_runtime_mutation()
    policy.require_runtime_mutation_allowed("podman create")


def test_execute_mode_helper_allows_runtime_mutation() -> None:
    ensure_runtime_mutation_allowed(RuntimePolicy(mode=EXECUTE), "podman create")


def test_unknown_runtime_mode_is_rejected() -> None:
    with pytest.raises(ValueError, match="unknown runtime mode"):
        RuntimePolicy(mode="unknown")

