from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from appresolver.environment import EnvironmentManifest, filename_for_environment_id, validate_environment_id
from appresolver.errors import AppNotFoundError, InvalidAppIdError, ManifestError, RegistryError


class EnvironmentRegistry:
    def __init__(self, environments_dir: Path) -> None:
        self.environments_dir = environments_dir

    def path_for(self, environment_id: str) -> Path:
        filename = filename_for_environment_id(environment_id)
        path = self.environments_dir / filename
        if path.name != filename:
            raise InvalidAppIdError("environment_id produced an unsafe registry filename")
        return path

    def save(self, manifest: EnvironmentManifest) -> None:
        validate_environment_id(manifest.environment_id)
        path = self.path_for(manifest.environment_id)
        try:
            self.environments_dir.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(manifest.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
        except OSError as exc:
            raise RegistryError(f"failed to save environment manifest for {manifest.environment_id}: {exc}") from exc

    def load(self, environment_id: str) -> EnvironmentManifest:
        path = self.path_for(environment_id)
        if not path.exists():
            raise AppNotFoundError(f"environment '{environment_id}' is not managed by App Resolver")

        try:
            raw_data: Any = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ManifestError(f"environment manifest for {environment_id} is not valid JSON: {exc}") from exc
        except OSError as exc:
            raise RegistryError(f"failed to read environment manifest for {environment_id}: {exc}") from exc

        if not isinstance(raw_data, dict):
            raise ManifestError(f"environment manifest for {environment_id} must be a JSON object")

        manifest = EnvironmentManifest.from_dict(raw_data)
        if manifest.environment_id != environment_id:
            raise ManifestError(
                "environment manifest environment_id "
                f"'{manifest.environment_id}' does not match requested environment_id '{environment_id}'"
            )
        validate_environment_id(manifest.environment_id)
        return manifest

    def list(self) -> list[EnvironmentManifest]:
        if not self.environments_dir.exists():
            return []
        if not self.environments_dir.is_dir():
            raise RegistryError(f"environment registry path is not a directory: {self.environments_dir}")

        manifests: list[EnvironmentManifest] = []
        for path in sorted(self.environments_dir.glob("*.json")):
            environment_id = path.stem
            manifests.append(self.load(environment_id))
        return sorted(manifests, key=lambda manifest: manifest.environment_id)

    def delete(self, environment_id: str) -> None:
        path = self.path_for(environment_id)
        if not path.exists():
            raise AppNotFoundError(f"environment '{environment_id}' is not managed by App Resolver")

        try:
            path.unlink()
        except OSError as exc:
            raise RegistryError(f"failed to delete environment manifest for {environment_id}: {exc}") from exc

    def exists(self, environment_id: str) -> bool:
        return self.path_for(environment_id).exists()

