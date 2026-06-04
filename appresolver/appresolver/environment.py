from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any

from appresolver.errors import InvalidAppIdError, ManifestError


JsonObject = dict[str, Any]
PackageRecord = dict[str, str]

ENVIRONMENT_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


def validate_environment_id(environment_id: str) -> str:
    if not isinstance(environment_id, str) or not environment_id:
        raise InvalidAppIdError("environment_id must be a non-empty string")
    if not ENVIRONMENT_ID_PATTERN.fullmatch(environment_id):
        raise InvalidAppIdError(
            "environment_id must match ^[A-Za-z0-9][A-Za-z0-9._-]*$ and cannot contain path separators"
        )
    return environment_id


def filename_for_environment_id(environment_id: str) -> str:
    return f"{validate_environment_id(environment_id)}.json"


@dataclass(frozen=True)
class EnvironmentManifest:
    environment_id: str
    name: str
    backend: str
    image: str
    status: str
    created_at: str
    permissions: JsonObject
    apps: list[str]
    source: JsonObject

    def __post_init__(self) -> None:
        validate_environment_id(self.environment_id)
        required_values = {
            "environment_id": self.environment_id,
            "name": self.name,
            "backend": self.backend,
            "image": self.image,
            "status": self.status,
            "created_at": self.created_at,
        }
        for field_name, value in required_values.items():
            if not isinstance(value, str) or not value.strip():
                raise ManifestError(f"environment manifest field '{field_name}' must be a non-empty string")

        if not isinstance(self.permissions, dict):
            raise ManifestError("environment manifest field 'permissions' must be an object")
        if not isinstance(self.apps, list):
            raise ManifestError("environment manifest field 'apps' must be a list")
        if not all(isinstance(app_id, str) and app_id for app_id in self.apps):
            raise ManifestError("environment manifest field 'apps' must contain only non-empty strings")
        if not isinstance(self.source, dict):
            raise ManifestError("environment manifest field 'source' must be an object")

    def to_dict(self) -> JsonObject:
        return asdict(self)

    def installed_packages(self) -> list[PackageRecord]:
        raw_packages = self.source.get("installed_packages", [])
        if not isinstance(raw_packages, list):
            raise ManifestError("environment manifest source.installed_packages must be a list")

        packages: list[PackageRecord] = []
        for raw_package in raw_packages:
            if not isinstance(raw_package, dict):
                raise ManifestError("environment manifest source.installed_packages must contain objects")
            name = raw_package.get("name")
            manager = raw_package.get("manager")
            installed_at = raw_package.get("installed_at")
            if not isinstance(name, str) or not name:
                raise ManifestError("environment package record field 'name' must be a non-empty string")
            if not isinstance(manager, str) or not manager:
                raise ManifestError("environment package record field 'manager' must be a non-empty string")
            if not isinstance(installed_at, str) or not installed_at:
                raise ManifestError("environment package record field 'installed_at' must be a non-empty string")
            packages.append({"name": name, "manager": manager, "installed_at": installed_at})
        return packages

    def with_installed_package(self, name: str, manager: str, installed_at: str) -> EnvironmentManifest:
        packages = self.installed_packages()
        if any(package["name"] == name for package in packages):
            return self

        source = dict(self.source)
        source["installed_packages"] = [
            *packages,
            {"name": name, "manager": manager, "installed_at": installed_at},
        ]
        return EnvironmentManifest(
            environment_id=self.environment_id,
            name=self.name,
            backend=self.backend,
            image=self.image,
            status=self.status,
            created_at=self.created_at,
            permissions=self.permissions,
            apps=self.apps,
            source=source,
        )

    def without_installed_packages(self) -> EnvironmentManifest:
        self.installed_packages()
        source = dict(self.source)
        source.pop("installed_packages", None)
        return EnvironmentManifest(
            environment_id=self.environment_id,
            name=self.name,
            backend=self.backend,
            image=self.image,
            status=self.status,
            created_at=self.created_at,
            permissions=self.permissions,
            apps=self.apps,
            source=source,
        )

    def without_installed_package(self, name: str) -> EnvironmentManifest:
        packages = [package for package in self.installed_packages() if package["name"] != name]
        source = dict(self.source)
        if packages:
            source["installed_packages"] = packages
        else:
            source.pop("installed_packages", None)
        return EnvironmentManifest(
            environment_id=self.environment_id,
            name=self.name,
            backend=self.backend,
            image=self.image,
            status=self.status,
            created_at=self.created_at,
            permissions=self.permissions,
            apps=self.apps,
            source=source,
        )

    @classmethod
    def from_dict(cls, data: JsonObject) -> EnvironmentManifest:
        try:
            return cls(
                environment_id=data["environment_id"],
                name=data["name"],
                backend=data["backend"],
                image=data["image"],
                status=data["status"],
                created_at=data["created_at"],
                permissions=data["permissions"],
                apps=data["apps"],
                source=data["source"],
            )
        except KeyError as exc:
            raise ManifestError(f"environment manifest is missing required field '{exc.args[0]}'") from exc
