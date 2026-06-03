from __future__ import annotations

from dataclasses import dataclass

from appresolver.errors import RuntimeActionBlocked


PLAN_ONLY = "plan-only"
EXECUTE = "execute"
VALID_RUNTIME_MODES = {PLAN_ONLY, EXECUTE}


@dataclass(frozen=True)
class RuntimePolicy:
    mode: str = PLAN_ONLY

    def __post_init__(self) -> None:
        if self.mode not in VALID_RUNTIME_MODES:
            raise ValueError(f"unknown runtime mode: {self.mode}")

    def allows_runtime_mutation(self) -> bool:
        return self.mode == EXECUTE

    def require_runtime_mutation_allowed(self, action: str) -> None:
        if self.allows_runtime_mutation():
            return
        raise RuntimeActionBlocked(f"runtime action '{action}' is blocked in {PLAN_ONLY} mode")


def default_runtime_policy() -> RuntimePolicy:
    return RuntimePolicy()


def ensure_runtime_mutation_allowed(policy: RuntimePolicy, action: str) -> None:
    policy.require_runtime_mutation_allowed(action)

