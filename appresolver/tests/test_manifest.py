from __future__ import annotations

import pytest

from appresolver.errors import ManifestError
from appresolver.manifest import AppManifest


def make_manifest(app_id: str = "com.example.App") -> AppManifest:
    return AppManifest(
        app_id=app_id,
        name="Example App",
        backend="flatpak",
        source={"type": "flatpak", "remote": "flathub", "app_id": app_id},
        permissions={"flatpak": {"Context": {"shared": "network"}}},
        trust_tier="community",
        installed_at="2026-06-03T12:00:00+00:00",
    )


def test_manifest_round_trips_through_dict() -> None:
    manifest = make_manifest()

    loaded = AppManifest.from_dict(manifest.to_dict())

    assert loaded == manifest


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("app_id", ""),
        ("name", ""),
        ("backend", ""),
        ("trust_tier", ""),
        ("installed_at", ""),
    ],
)
def test_manifest_rejects_empty_required_string_fields(field_name: str, value: str) -> None:
    data = make_manifest().to_dict()
    data[field_name] = value

    with pytest.raises(ManifestError, match=field_name):
        AppManifest.from_dict(data)


def test_manifest_rejects_missing_required_field() -> None:
    data = make_manifest().to_dict()
    del data["backend"]

    with pytest.raises(ManifestError, match="backend"):
        AppManifest.from_dict(data)


def test_manifest_rejects_non_object_source() -> None:
    data = make_manifest().to_dict()
    data["source"] = "flatpak"

    with pytest.raises(ManifestError, match="source"):
        AppManifest.from_dict(data)


def test_manifest_rejects_non_object_permissions() -> None:
    data = make_manifest().to_dict()
    data["permissions"] = []

    with pytest.raises(ManifestError, match="permissions"):
        AppManifest.from_dict(data)

