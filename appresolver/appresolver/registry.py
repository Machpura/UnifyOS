from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from appresolver.errors import AppNotFoundError, InvalidAppIdError, ManifestError, RegistryError
from appresolver.manifest import AppManifest
from appresolver.state import StatePaths


APP_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


def default_registry_dir() -> Path:
    return StatePaths.default().apps_dir


def validate_app_id(app_id: str) -> str:
    if not isinstance(app_id, str) or not app_id:
        raise InvalidAppIdError("app_id must be a non-empty string")
    if not APP_ID_PATTERN.fullmatch(app_id):
        raise InvalidAppIdError(
            "app_id must match ^[A-Za-z0-9][A-Za-z0-9._-]*$ and cannot contain path separators"
        )
    return app_id


def filename_for_app_id(app_id: str) -> str:
    return f"{validate_app_id(app_id)}.json"


class AppRegistry:
    def __init__(self, registry_dir: Path) -> None:
        self.registry_dir = registry_dir

    def path_for(self, app_id: str) -> Path:
        filename = filename_for_app_id(app_id)
        path = self.registry_dir / filename
        if path.name != filename:
            raise InvalidAppIdError("app_id produced an unsafe registry filename")
        return path

    def save(self, manifest: AppManifest) -> None:
        validate_app_id(manifest.app_id)
        path = self.path_for(manifest.app_id)
        try:
            self.registry_dir.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(manifest.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
        except OSError as exc:
            raise RegistryError(f"failed to save manifest for {manifest.app_id}: {exc}") from exc

    def load(self, app_id: str) -> AppManifest:
        path = self.path_for(app_id)
        if not path.exists():
            raise AppNotFoundError(f"app '{app_id}' is not managed by App Resolver")

        try:
            raw_data: Any = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ManifestError(f"manifest for {app_id} is not valid JSON: {exc}") from exc
        except OSError as exc:
            raise RegistryError(f"failed to read manifest for {app_id}: {exc}") from exc

        if not isinstance(raw_data, dict):
            raise ManifestError(f"manifest for {app_id} must be a JSON object")

        manifest = AppManifest.from_dict(raw_data)
        if manifest.app_id != app_id:
            raise ManifestError(f"manifest app_id '{manifest.app_id}' does not match requested app_id '{app_id}'")
        validate_app_id(manifest.app_id)
        return manifest

    def list(self) -> list[AppManifest]:
        if not self.registry_dir.exists():
            return []
        if not self.registry_dir.is_dir():
            raise RegistryError(f"registry path is not a directory: {self.registry_dir}")

        manifests: list[AppManifest] = []
        for path in sorted(self.registry_dir.glob("*.json")):
            app_id = path.stem
            manifests.append(self.load(app_id))
        return sorted(manifests, key=lambda manifest: manifest.app_id)

    def delete(self, app_id: str) -> None:
        path = self.path_for(app_id)
        if not path.exists():
            raise AppNotFoundError(f"app '{app_id}' is not managed by App Resolver")

        try:
            path.unlink()
        except OSError as exc:
            raise RegistryError(f"failed to delete manifest for {app_id}: {exc}") from exc

    def exists(self, app_id: str) -> bool:
        return self.path_for(app_id).exists()
