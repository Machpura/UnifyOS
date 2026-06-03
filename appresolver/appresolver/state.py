from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from appresolver.errors import BackendError


@dataclass(frozen=True)
class StatePaths:
    state_root: Path
    apps_dir: Path
    appimages_dir: Path
    launchers_dir: Path
    logs_dir: Path
    environments_dir: Path

    @classmethod
    def from_registry_dir(cls, registry_dir: Path) -> StatePaths:
        state_root = registry_dir.parent
        return cls(
            state_root=state_root,
            apps_dir=registry_dir,
            appimages_dir=state_root / "appimages",
            launchers_dir=state_root / "launchers",
            logs_dir=state_root / "logs",
            environments_dir=state_root / "environments",
        )

    @classmethod
    def default(cls) -> StatePaths:
        return cls.from_registry_dir(Path.cwd() / ".appresolver" / "apps")

    def resolved_state_root(self) -> Path:
        return self.state_root.resolve(strict=False)

    def validate_inside_state_root(self, path: Path) -> Path:
        resolved_path = path.resolve(strict=False)
        resolved_root = self.resolved_state_root()
        if resolved_path == resolved_root or resolved_path.is_relative_to(resolved_root):
            return resolved_path
        raise BackendError(f"managed path is outside resolver state: {path}")

