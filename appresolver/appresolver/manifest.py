from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any

from appresolver.errors import ManifestError


JsonObject = dict[str, Any]


@dataclass(frozen=True)
class AppManifest:
    app_id: str
    name: str
    backend: str
    source: JsonObject
    permissions: JsonObject
    trust_tier: str
    installed_at: str

    def __post_init__(self) -> None:
        required_values = {
            "app_id": self.app_id,
            "name": self.name,
            "backend": self.backend,
            "trust_tier": self.trust_tier,
            "installed_at": self.installed_at,
        }
        for field_name, value in required_values.items():
            if not isinstance(value, str) or not value.strip():
                raise ManifestError(f"manifest field '{field_name}' must be a non-empty string")

        if not isinstance(self.source, dict):
            raise ManifestError("manifest field 'source' must be an object")
        if not isinstance(self.permissions, dict):
            raise ManifestError("manifest field 'permissions' must be an object")

    def to_dict(self) -> JsonObject:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: JsonObject) -> AppManifest:
        try:
            return cls(
                app_id=data["app_id"],
                name=data["name"],
                backend=data["backend"],
                source=data["source"],
                permissions=data["permissions"],
                trust_tier=data["trust_tier"],
                installed_at=data["installed_at"],
            )
        except KeyError as exc:
            raise ManifestError(f"manifest is missing required field '{exc.args[0]}'") from exc


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()

