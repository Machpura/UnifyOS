from __future__ import annotations

import json
from pathlib import Path

import pytest

from appresolver.environment import EnvironmentManifest
from appresolver.environment_registry import EnvironmentRegistry
from appresolver.errors import AppNotFoundError, InvalidAppIdError, ManifestError, RegistryError
from appresolver.state import StatePaths


def make_environment_manifest(environment_id: str = "ubuntu-24.04-default") -> EnvironmentManifest:
    return EnvironmentManifest(
        environment_id=environment_id,
        name=environment_id,
        backend="container",
        image="ubuntu:24.04",
        status="defined",
        created_at="2026-06-03T12:00:00+00:00",
        permissions={},
        apps=[],
        source={"type": "manual"},
    )


def test_environment_registry_saves_manifest_with_safe_filename(tmp_path: Path) -> None:
    state_paths = StatePaths.from_registry_dir(tmp_path / ".appresolver" / "apps")
    registry = EnvironmentRegistry(state_paths.environments_dir)
    manifest = make_environment_manifest("ubuntu-24.04-default")

    registry.save(manifest)

    assert (state_paths.environments_dir / "ubuntu-24.04-default.json").exists()


def test_environment_registry_save_refuses_to_overwrite_existing_manifest(tmp_path: Path) -> None:
    registry = EnvironmentRegistry(tmp_path)
    registry.save(make_environment_manifest("ubuntu-24.04-default"))

    with pytest.raises(RegistryError, match="already managed"):
        registry.save(make_environment_manifest("ubuntu-24.04-default"))

    assert registry.load("ubuntu-24.04-default").image == "ubuntu:24.04"


def test_environment_registry_update_replaces_existing_manifest(tmp_path: Path) -> None:
    registry = EnvironmentRegistry(tmp_path)
    manifest = make_environment_manifest("ubuntu-24.04-default")
    registry.save(manifest)

    registry.update(
        EnvironmentManifest(
            environment_id=manifest.environment_id,
            name=manifest.name,
            backend=manifest.backend,
            image=manifest.image,
            status="created",
            created_at=manifest.created_at,
            permissions=manifest.permissions,
            apps=manifest.apps,
            source=manifest.source,
        )
    )

    assert registry.load("ubuntu-24.04-default").status == "created"


def test_environment_registry_update_missing_manifest_raises_clear_error(tmp_path: Path) -> None:
    registry = EnvironmentRegistry(tmp_path)

    with pytest.raises(AppNotFoundError, match="not managed"):
        registry.update(make_environment_manifest("ubuntu-24.04-default"))


def test_environment_registry_failed_save_leaves_no_final_or_temp_manifest(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    registry = EnvironmentRegistry(tmp_path)
    original_write_text = Path.write_text

    def failing_write_text(path: Path, *args: object, **kwargs: object) -> int:
        if path.name == ".ubuntu-24.04-default.json.tmp":
            original_write_text(path, "partial", encoding="utf-8")
            raise OSError("blocked")
        return original_write_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", failing_write_text)

    with pytest.raises(RegistryError, match="failed to save"):
        registry.save(make_environment_manifest("ubuntu-24.04-default"))

    assert not (tmp_path / "ubuntu-24.04-default.json").exists()
    assert not (tmp_path / ".ubuntu-24.04-default.json.tmp").exists()


def test_environment_registry_failed_update_keeps_existing_manifest_and_removes_temp(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    registry = EnvironmentRegistry(tmp_path)
    registry.save(make_environment_manifest("ubuntu-24.04-default"))
    original_write_text = Path.write_text

    def failing_write_text(path: Path, *args: object, **kwargs: object) -> int:
        if path.name == ".ubuntu-24.04-default.json.tmp":
            original_write_text(path, "partial", encoding="utf-8")
            raise OSError("blocked")
        return original_write_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", failing_write_text)

    with pytest.raises(RegistryError, match="failed to update"):
        registry.update(
            EnvironmentManifest(
                environment_id="ubuntu-24.04-default",
                name="ubuntu-24.04-default",
                backend="container",
                image="ubuntu:24.04",
                status="created",
                created_at="2026-06-03T12:00:00+00:00",
                permissions={},
                apps=[],
                source={"type": "manual"},
            )
        )

    assert registry.load("ubuntu-24.04-default").status == "defined"
    assert not (tmp_path / ".ubuntu-24.04-default.json.tmp").exists()


def test_environment_registry_loads_saved_manifest(tmp_path: Path) -> None:
    registry = EnvironmentRegistry(tmp_path)
    manifest = make_environment_manifest()
    registry.save(manifest)

    loaded = registry.load(manifest.environment_id)

    assert loaded == manifest


def test_environment_registry_load_rejects_invalid_json(tmp_path: Path) -> None:
    registry = EnvironmentRegistry(tmp_path)
    (tmp_path / "ubuntu-24.04-default.json").write_text("{", encoding="utf-8")

    with pytest.raises(ManifestError, match="not valid JSON"):
        registry.load("ubuntu-24.04-default")


def test_environment_registry_load_rejects_non_object_json(tmp_path: Path) -> None:
    registry = EnvironmentRegistry(tmp_path)
    (tmp_path / "ubuntu-24.04-default.json").write_text("[]", encoding="utf-8")

    with pytest.raises(ManifestError, match="must be a JSON object"):
        registry.load("ubuntu-24.04-default")


def test_environment_registry_load_rejects_missing_required_field(tmp_path: Path) -> None:
    registry = EnvironmentRegistry(tmp_path)
    data = make_environment_manifest().to_dict()
    del data["backend"]
    (tmp_path / "ubuntu-24.04-default.json").write_text(json.dumps(data), encoding="utf-8")

    with pytest.raises(ManifestError, match="backend"):
        registry.load("ubuntu-24.04-default")


def test_environment_registry_load_rejects_environment_id_mismatch(tmp_path: Path) -> None:
    registry = EnvironmentRegistry(tmp_path)
    data = make_environment_manifest("fedora-latest").to_dict()
    (tmp_path / "ubuntu-24.04-default.json").write_text(json.dumps(data), encoding="utf-8")

    with pytest.raises(ManifestError, match="does not match"):
        registry.load("ubuntu-24.04-default")


def test_environment_registry_lists_manifests_sorted_by_environment_id(tmp_path: Path) -> None:
    registry = EnvironmentRegistry(tmp_path)
    registry.save(make_environment_manifest("ubuntu-24.04-default"))
    registry.save(make_environment_manifest("fedora-latest"))
    registry.save(make_environment_manifest("arch-community"))

    environment_ids = [manifest.environment_id for manifest in registry.list()]

    assert environment_ids == ["arch-community", "fedora-latest", "ubuntu-24.04-default"]


def test_environment_registry_delete_removes_manifest(tmp_path: Path) -> None:
    registry = EnvironmentRegistry(tmp_path)
    manifest = make_environment_manifest()
    registry.save(manifest)

    registry.delete(manifest.environment_id)

    assert not registry.exists(manifest.environment_id)


def test_environment_registry_delete_refuses_symlink_resolving_outside_registry(tmp_path: Path) -> None:
    registry = EnvironmentRegistry(tmp_path / "environments")
    outside_file = tmp_path / "outside.json"
    outside_file.write_text("outside", encoding="utf-8")
    registry.environments_dir.mkdir()
    manifest_path = registry.path_for("ubuntu-24.04-default")
    manifest_path.symlink_to(outside_file)

    with pytest.raises(RegistryError, match="outside environment registry"):
        registry.delete("ubuntu-24.04-default")

    assert outside_file.exists()
    assert manifest_path.exists()


def test_environment_registry_delete_missing_manifest_raises_clear_error(tmp_path: Path) -> None:
    registry = EnvironmentRegistry(tmp_path)

    with pytest.raises(AppNotFoundError, match="not managed"):
        registry.delete("ubuntu-24.04-default")


def test_environment_registry_load_missing_manifest_raises_clear_error(tmp_path: Path) -> None:
    registry = EnvironmentRegistry(tmp_path)

    with pytest.raises(AppNotFoundError, match="not managed"):
        registry.load("ubuntu-24.04-default")


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
def test_environment_registry_rejects_unsafe_environment_ids(tmp_path: Path, environment_id: str) -> None:
    registry = EnvironmentRegistry(tmp_path)

    with pytest.raises(InvalidAppIdError):
        registry.path_for(environment_id)


def test_environment_registry_constructor_creates_no_directory(tmp_path: Path) -> None:
    environments_dir = tmp_path / ".appresolver" / "environments"

    EnvironmentRegistry(environments_dir)

    assert not environments_dir.exists()
