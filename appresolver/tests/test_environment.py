from __future__ import annotations

import pytest

from appresolver.environment import EnvironmentManifest, filename_for_environment_id, validate_environment_id
from appresolver.errors import InvalidAppIdError, ManifestError


def make_environment_manifest(environment_id: str = "ubuntu-24.04-default") -> EnvironmentManifest:
    return EnvironmentManifest(
        environment_id=environment_id,
        name="Ubuntu 24.04 Default",
        backend="container",
        image="ubuntu:24.04",
        status="defined",
        created_at="2026-06-03T12:00:00+00:00",
        permissions={"files": {}, "devices": {}, "network": {}},
        apps=["com.example.App"],
        source={"type": "manual"},
    )


def test_environment_manifest_round_trips_through_dict() -> None:
    manifest = make_environment_manifest()

    loaded = EnvironmentManifest.from_dict(manifest.to_dict())

    assert loaded == manifest


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("environment_id", ""),
        ("name", ""),
        ("backend", ""),
        ("image", ""),
        ("status", ""),
        ("created_at", ""),
    ],
)
def test_environment_manifest_rejects_empty_required_string_fields(field_name: str, value: str) -> None:
    data = make_environment_manifest().to_dict()
    data[field_name] = value

    expected_error = InvalidAppIdError if field_name == "environment_id" else ManifestError
    with pytest.raises(expected_error, match=field_name):
        EnvironmentManifest.from_dict(data)


def test_environment_manifest_rejects_missing_required_field() -> None:
    data = make_environment_manifest().to_dict()
    del data["backend"]

    with pytest.raises(ManifestError, match="backend"):
        EnvironmentManifest.from_dict(data)


def test_environment_manifest_rejects_non_object_permissions() -> None:
    data = make_environment_manifest().to_dict()
    data["permissions"] = []

    with pytest.raises(ManifestError, match="permissions"):
        EnvironmentManifest.from_dict(data)


def test_environment_manifest_rejects_non_list_apps() -> None:
    data = make_environment_manifest().to_dict()
    data["apps"] = "com.example.App"

    with pytest.raises(ManifestError, match="apps"):
        EnvironmentManifest.from_dict(data)


@pytest.mark.parametrize("apps", [[""], ["com.example.App", 123], [None]])
def test_environment_manifest_rejects_non_string_app_entries(apps: list[object]) -> None:
    data = make_environment_manifest().to_dict()
    data["apps"] = apps

    with pytest.raises(ManifestError, match="apps"):
        EnvironmentManifest.from_dict(data)


def test_environment_manifest_rejects_non_object_source() -> None:
    data = make_environment_manifest().to_dict()
    data["source"] = "manual"

    with pytest.raises(ManifestError, match="source"):
        EnvironmentManifest.from_dict(data)


def test_environment_manifest_without_installed_packages_returns_empty_list() -> None:
    manifest = make_environment_manifest()

    assert manifest.installed_packages() == []


def test_environment_manifest_with_installed_package_adds_record_under_source() -> None:
    manifest = make_environment_manifest()

    updated = manifest.with_installed_package("curl", "apt", "2026-06-03T12:00:00+00:00")

    assert updated.source["type"] == "manual"
    assert updated.installed_packages() == [
        {"name": "curl", "manager": "apt", "installed_at": "2026-06-03T12:00:00+00:00"}
    ]


def test_environment_manifest_with_installed_package_does_not_duplicate_existing_record() -> None:
    manifest = make_environment_manifest().with_installed_package(
        "curl", "apt", "2026-06-03T12:00:00+00:00"
    )

    updated = manifest.with_installed_package("curl", "apt", "2026-06-03T13:00:00+00:00")

    assert updated.installed_packages() == [
        {"name": "curl", "manager": "apt", "installed_at": "2026-06-03T12:00:00+00:00"}
    ]


def test_environment_manifest_without_installed_packages_clears_records_and_preserves_source() -> None:
    manifest = make_environment_manifest().with_installed_package(
        "curl", "apt", "2026-06-03T12:00:00+00:00"
    )

    updated = manifest.without_installed_packages()

    assert updated.source == {"type": "manual"}
    assert updated.installed_packages() == []


def test_environment_manifest_without_installed_package_removes_one_record() -> None:
    manifest = (
        make_environment_manifest()
        .with_installed_package("curl", "apt", "2026-06-03T12:00:00+00:00")
        .with_installed_package("wget", "apt", "2026-06-03T13:00:00+00:00")
    )

    updated = manifest.without_installed_package("curl")

    assert updated.installed_packages() == [
        {"name": "wget", "manager": "apt", "installed_at": "2026-06-03T13:00:00+00:00"}
    ]
    assert updated.source["type"] == "manual"


def test_environment_manifest_without_installed_package_removes_key_when_empty() -> None:
    manifest = make_environment_manifest().with_installed_package(
        "curl", "apt", "2026-06-03T12:00:00+00:00"
    )

    updated = manifest.without_installed_package("curl")

    assert updated.installed_packages() == []
    assert "installed_packages" not in updated.source


@pytest.mark.parametrize(
    "installed_packages",
    [
        "curl",
        ["curl"],
        [{"manager": "apt", "installed_at": "2026-06-03T12:00:00+00:00"}],
        [{"name": "curl", "installed_at": "2026-06-03T12:00:00+00:00"}],
        [{"name": "curl", "manager": "apt"}],
    ],
)
def test_environment_manifest_rejects_malformed_installed_packages(installed_packages: object) -> None:
    manifest = EnvironmentManifest.from_dict(
        {
            **make_environment_manifest().to_dict(),
            "source": {"type": "manual", "installed_packages": installed_packages},
        }
    )

    with pytest.raises(ManifestError):
        manifest.installed_packages()


@pytest.mark.parametrize(
    "environment_id",
    [
        "",
        "../x",
        "a/b",
        "a\\b",
        ".hidden",
        "-bad",
        "bad env",
        "bad$env",
    ],
)
def test_validate_environment_id_rejects_unsafe_ids(environment_id: str) -> None:
    with pytest.raises(InvalidAppIdError):
        validate_environment_id(environment_id)


def test_validate_environment_id_accepts_safe_id() -> None:
    assert validate_environment_id("ubuntu-24.04-default") == "ubuntu-24.04-default"


def test_filename_for_environment_id_uses_allowlisted_id() -> None:
    assert filename_for_environment_id("ubuntu-24.04-default") == "ubuntu-24.04-default.json"
