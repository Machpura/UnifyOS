from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from pytest import CaptureFixture

from appresolver.backends.appimage import appimages_dir_for_registry, launcher_path, launchers_dir_for_registry, managed_appimage_path
from appresolver.backends import flatpak
from appresolver.cli import main
from appresolver.environment_registry import EnvironmentRegistry
from appresolver.errors import CommandExecutionError, RegistryError
from appresolver.manifest import AppManifest
from appresolver.registry import AppRegistry
from appresolver.state import StatePaths


def make_manifest(app_id: str = "com.example.App") -> AppManifest:
    return AppManifest(
        app_id=app_id,
        name=app_id,
        backend="flatpak",
        source={"type": "flatpak", "remote": "flathub", "app_id": app_id},
        permissions={"flatpak": {"Context": {"shared": "network"}}},
        trust_tier="community",
        installed_at="2026-06-03T12:00:00+00:00",
    )


def make_appimage_manifest(registry_dir: Path, app_id: str = "Example") -> AppManifest:
    return AppManifest(
        app_id=app_id,
        name=app_id,
        backend="appimage",
        source={
            "type": "appimage",
            "original_path": str(registry_dir.parent / "source" / f"{app_id}.AppImage"),
            "managed_path": str(managed_appimage_path(registry_dir, app_id)),
            "launcher_path": str(launcher_path(registry_dir, app_id)),
        },
        permissions={"appimage": {"sandboxed": False, "executed_during_import": False}},
        trust_tier="unverified",
        installed_at="2026-06-03T12:00:00+00:00",
    )


def write_appimage(path: Path, content: str = "#!/bin/sh\nexit 0\n") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def test_global_json_flag_before_list_outputs_json_array(tmp_path: Path, capsys: CaptureFixture[str]) -> None:
    registry = AppRegistry(tmp_path)
    registry.save(make_manifest("com.example.App"))

    exit_code = main(["--registry-dir", str(tmp_path), "--json", "list"])

    assert exit_code == 0
    output = json.loads(capsys.readouterr().out)
    assert output == [
        {
            "app_id": "com.example.App",
            "name": "com.example.App",
            "backend": "flatpak",
            "trust_tier": "community",
            "installed_at": "2026-06-03T12:00:00+00:00",
            "source": {"type": "flatpak", "remote": "flathub", "app_id": "com.example.App"},
        }
    ]


def test_global_json_flag_before_permissions_outputs_json_object(
    tmp_path: Path, capsys: CaptureFixture[str]
) -> None:
    registry = AppRegistry(tmp_path)
    registry.save(make_manifest("com.example.App"))

    exit_code = main(["--registry-dir", str(tmp_path), "--json", "permissions", "com.example.App"])

    assert exit_code == 0
    output = json.loads(capsys.readouterr().out)
    assert output == {
        "app_id": "com.example.App",
        "permissions": {"flatpak": {"Context": {"shared": "network"}}},
    }


def test_subcommand_json_flag_still_works_for_list(tmp_path: Path, capsys: CaptureFixture[str]) -> None:
    registry = AppRegistry(tmp_path)
    registry.save(make_manifest("com.example.App"))

    exit_code = main(["--registry-dir", str(tmp_path), "list", "--json"])

    assert exit_code == 0
    output = json.loads(capsys.readouterr().out)
    assert output[0]["app_id"] == "com.example.App"


def test_list_human_output_is_unchanged(tmp_path: Path, capsys: CaptureFixture[str]) -> None:
    registry = AppRegistry(tmp_path)
    registry.save(make_manifest("com.example.App"))

    exit_code = main(["--registry-dir", str(tmp_path), "list"])

    assert exit_code == 0
    assert capsys.readouterr().out == "com.example.App\tflatpak\tcommunity\n"


def test_global_dry_run_before_install_flatpak_does_not_write_manifest(
    tmp_path: Path, capsys: CaptureFixture[str]
) -> None:
    exit_code = main(["--registry-dir", str(tmp_path), "--dry-run", "install-flatpak", "com.discordapp.Discord"])

    assert exit_code == 0
    assert not (tmp_path / "com.discordapp.Discord.json").exists()
    assert "Would run: flatpak install -y flathub com.discordapp.Discord" in capsys.readouterr().out


def test_global_dry_run_before_uninstall_does_not_delete_manifest(
    tmp_path: Path, capsys: CaptureFixture[str]
) -> None:
    registry = AppRegistry(tmp_path)
    registry.save(make_manifest("com.discordapp.Discord"))

    exit_code = main(["--registry-dir", str(tmp_path), "--dry-run", "uninstall", "com.discordapp.Discord"])

    assert exit_code == 0
    assert (tmp_path / "com.discordapp.Discord.json").exists()
    assert "Would run: flatpak uninstall -y com.discordapp.Discord" in capsys.readouterr().out


def test_subcommand_dry_run_install_flatpak_does_not_write_manifest(
    tmp_path: Path, capsys: CaptureFixture[str]
) -> None:
    exit_code = main(["--registry-dir", str(tmp_path), "install-flatpak", "com.discordapp.Discord", "--dry-run"])

    assert exit_code == 0
    assert not (tmp_path / "com.discordapp.Discord.json").exists()
    assert "Would write manifest:" in capsys.readouterr().out


def test_subcommand_dry_run_uninstall_does_not_delete_manifest(
    tmp_path: Path, capsys: CaptureFixture[str]
) -> None:
    registry = AppRegistry(tmp_path)
    registry.save(make_manifest("com.discordapp.Discord"))

    exit_code = main(["--registry-dir", str(tmp_path), "uninstall", "com.discordapp.Discord", "--dry-run"])

    assert exit_code == 0
    assert (tmp_path / "com.discordapp.Discord.json").exists()
    assert "Would delete manifest:" in capsys.readouterr().out


def test_dry_run_install_does_not_require_flatpak(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    def fail_require_flatpak() -> None:
        raise AssertionError("dry-run must not require Flatpak")

    monkeypatch.setattr(flatpak, "require_flatpak", fail_require_flatpak)

    exit_code = main(["--registry-dir", str(tmp_path), "--dry-run", "install-flatpak", "com.discordapp.Discord"])

    assert exit_code == 0
    assert not (tmp_path / "com.discordapp.Discord.json").exists()


def test_dry_run_uninstall_does_not_require_flatpak(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    def fail_require_flatpak() -> None:
        raise AssertionError("dry-run must not require Flatpak")

    registry = AppRegistry(tmp_path)
    registry.save(make_manifest("com.discordapp.Discord"))
    monkeypatch.setattr(flatpak, "require_flatpak", fail_require_flatpak)

    exit_code = main(["--registry-dir", str(tmp_path), "--dry-run", "uninstall", "com.discordapp.Discord"])

    assert exit_code == 0
    assert (tmp_path / "com.discordapp.Discord.json").exists()


def test_install_flatpak_does_not_save_manifest_when_flatpak_install_fails(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def fake_run_command(command: list[str]) -> subprocess.CompletedProcess[str]:
        raise CommandExecutionError(f"failed: {' '.join(command)}")

    monkeypatch.setattr(flatpak, "require_flatpak", lambda: None)
    monkeypatch.setattr(flatpak, "run_command", fake_run_command)

    exit_code = main(["--registry-dir", str(tmp_path), "install-flatpak", "com.discordapp.Discord"])

    assert exit_code == 1
    assert not (tmp_path / "com.discordapp.Discord.json").exists()


def test_install_flatpak_does_not_save_manifest_when_permission_inspection_fails(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls: list[list[str]] = []

    def fake_run_command(command: list[str]) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        if command == ["flatpak", "info", "--show-permissions", "com.discordapp.Discord"]:
            raise CommandExecutionError("permission inspection failed")
        return subprocess.CompletedProcess(args=command, returncode=0, stdout="", stderr="")

    monkeypatch.setattr(flatpak, "require_flatpak", lambda: None)
    monkeypatch.setattr(flatpak, "run_command", fake_run_command)

    exit_code = main(["--registry-dir", str(tmp_path), "install-flatpak", "com.discordapp.Discord"])

    assert exit_code == 1
    assert not (tmp_path / "com.discordapp.Discord.json").exists()
    assert ["flatpak", "uninstall", "-y", "com.discordapp.Discord"] not in calls


def test_uninstall_does_not_delete_manifest_when_flatpak_uninstall_fails(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def fake_run_command(command: list[str]) -> subprocess.CompletedProcess[str]:
        raise CommandExecutionError(f"failed: {' '.join(command)}")

    registry = AppRegistry(tmp_path)
    registry.save(make_manifest("com.discordapp.Discord"))
    monkeypatch.setattr(flatpak, "require_flatpak", lambda: None)
    monkeypatch.setattr(flatpak, "run_command", fake_run_command)

    exit_code = main(["--registry-dir", str(tmp_path), "uninstall", "com.discordapp.Discord"])

    assert exit_code == 1
    assert (tmp_path / "com.discordapp.Discord.json").exists()


def test_import_appimage_writes_managed_file_launcher_and_manifest(
    tmp_path: Path, capsys: CaptureFixture[str]
) -> None:
    registry_dir = tmp_path / ".appresolver" / "apps"
    source_path = write_appimage(tmp_path / "downloads" / "Example.AppImage")

    exit_code = main(["--registry-dir", str(registry_dir), "import-appimage", str(source_path)])

    assert exit_code == 0
    assert managed_appimage_path(registry_dir, "Example").exists()
    assert launcher_path(registry_dir, "Example").exists()
    assert AppRegistry(registry_dir).load("Example").backend == "appimage"
    assert capsys.readouterr().out.startswith("Imported Example as managed AppImage\n")


def test_import_appimage_with_custom_registry_dir_uses_sibling_state_dirs(tmp_path: Path) -> None:
    registry_dir = tmp_path / "custom-state" / "apps"
    source_path = write_appimage(tmp_path / "downloads" / "Example.AppImage")

    exit_code = main(["--registry-dir", str(registry_dir), "import-appimage", str(source_path)])

    assert exit_code == 0
    assert (tmp_path / "custom-state" / "apps" / "Example.json").exists()
    assert (tmp_path / "custom-state" / "appimages" / "Example.AppImage").exists()
    assert (tmp_path / "custom-state" / "launchers" / "Example.desktop").exists()
    assert not (tmp_path / ".appresolver").exists()


def test_dry_run_import_appimage_mutates_nothing(tmp_path: Path, capsys: CaptureFixture[str]) -> None:
    registry_dir = tmp_path / ".appresolver" / "apps"
    source_path = write_appimage(tmp_path / "downloads" / "Example.AppImage")

    exit_code = main(["--registry-dir", str(registry_dir), "--dry-run", "import-appimage", str(source_path)])

    assert exit_code == 0
    assert not registry_dir.exists()
    assert not appimages_dir_for_registry(registry_dir).exists()
    assert not launchers_dir_for_registry(registry_dir).exists()
    assert not managed_appimage_path(registry_dir, "Example").exists()
    assert not launcher_path(registry_dir, "Example").exists()
    assert "Would copy:" in capsys.readouterr().out


def test_subcommand_dry_run_import_appimage_mutates_nothing(
    tmp_path: Path, capsys: CaptureFixture[str]
) -> None:
    registry_dir = tmp_path / ".appresolver" / "apps"
    source_path = write_appimage(tmp_path / "downloads" / "Example.AppImage")

    exit_code = main(["--registry-dir", str(registry_dir), "import-appimage", str(source_path), "--dry-run"])

    assert exit_code == 0
    assert not registry_dir.exists()
    assert not appimages_dir_for_registry(registry_dir).exists()
    assert not launchers_dir_for_registry(registry_dir).exists()
    assert "Would write manifest:" in capsys.readouterr().out


def test_import_appimage_duplicate_app_id_does_not_overwrite_managed_file(tmp_path: Path) -> None:
    registry_dir = tmp_path / ".appresolver" / "apps"
    source_path = write_appimage(tmp_path / "downloads" / "Example.AppImage", "new")
    managed_path = managed_appimage_path(registry_dir, "Example")
    managed_path.parent.mkdir(parents=True)
    managed_path.write_text("existing", encoding="utf-8")
    AppRegistry(registry_dir).save(make_appimage_manifest(registry_dir, "Example"))

    exit_code = main(["--registry-dir", str(registry_dir), "import-appimage", str(source_path)])

    assert exit_code == 1
    assert managed_path.read_text(encoding="utf-8") == "existing"


def test_uninstall_appimage_removes_managed_file_launcher_and_manifest(tmp_path: Path) -> None:
    registry_dir = tmp_path / ".appresolver" / "apps"
    source_path = write_appimage(tmp_path / "downloads" / "Example.AppImage")
    main(["--registry-dir", str(registry_dir), "import-appimage", str(source_path)])

    exit_code = main(["--registry-dir", str(registry_dir), "uninstall", "Example"])

    assert exit_code == 0
    assert not managed_appimage_path(registry_dir, "Example").exists()
    assert not launcher_path(registry_dir, "Example").exists()
    assert not AppRegistry(registry_dir).exists("Example")


def test_uninstall_appimage_tolerates_missing_managed_files_and_deletes_manifest(tmp_path: Path) -> None:
    registry_dir = tmp_path / ".appresolver" / "apps"
    registry = AppRegistry(registry_dir)
    registry.save(make_appimage_manifest(registry_dir, "Example"))

    exit_code = main(["--registry-dir", str(registry_dir), "uninstall", "Example"])

    assert exit_code == 0
    assert not registry.exists("Example")


def test_dry_run_uninstall_appimage_mutates_nothing(tmp_path: Path, capsys: CaptureFixture[str]) -> None:
    registry_dir = tmp_path / ".appresolver" / "apps"
    registry = AppRegistry(registry_dir)
    manifest = make_appimage_manifest(registry_dir, "Example")
    registry.save(manifest)
    managed_path = Path(str(manifest.source["managed_path"]))
    desktop_path = Path(str(manifest.source["launcher_path"]))
    managed_path.parent.mkdir(parents=True)
    desktop_path.parent.mkdir(parents=True)
    managed_path.write_text("appimage", encoding="utf-8")
    desktop_path.write_text("launcher", encoding="utf-8")

    exit_code = main(["--registry-dir", str(registry_dir), "--dry-run", "uninstall", "Example"])

    assert exit_code == 0
    assert managed_path.exists()
    assert desktop_path.exists()
    assert registry.exists("Example")
    assert "Would remove managed AppImage:" in capsys.readouterr().out


def test_uninstall_appimage_file_removal_failure_keeps_manifest(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    registry_dir = tmp_path / ".appresolver" / "apps"
    source_path = write_appimage(tmp_path / "downloads" / "Example.AppImage")
    main(["--registry-dir", str(registry_dir), "import-appimage", str(source_path)])
    desktop_path = launcher_path(registry_dir, "Example")
    original_unlink = Path.unlink

    def failing_unlink(path: Path, *args: object, **kwargs: object) -> None:
        if path == desktop_path:
            raise OSError("blocked")
        original_unlink(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", failing_unlink)

    exit_code = main(["--registry-dir", str(registry_dir), "uninstall", "Example"])

    assert exit_code == 1
    assert AppRegistry(registry_dir).exists("Example")


def test_import_appimage_manifest_save_failure_cleans_up_managed_files(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    registry_dir = tmp_path / ".appresolver" / "apps"
    source_path = write_appimage(tmp_path / "downloads" / "Example.AppImage")

    def fail_save(self: AppRegistry, manifest: AppManifest) -> None:
        raise RegistryError("registry blocked")

    monkeypatch.setattr(AppRegistry, "save", fail_save)

    exit_code = main(["--registry-dir", str(registry_dir), "import-appimage", str(source_path)])

    assert exit_code == 1
    assert not managed_appimage_path(registry_dir, "Example").exists()
    assert not launcher_path(registry_dir, "Example").exists()
    assert not (registry_dir / "Example.json").exists()


def test_uninstall_appimage_outside_managed_path_keeps_manifest_and_outside_file(tmp_path: Path) -> None:
    registry_dir = tmp_path / ".appresolver" / "apps"
    registry = AppRegistry(registry_dir)
    manifest = make_appimage_manifest(registry_dir, "Example")
    outside_path = tmp_path / "outside.AppImage"
    outside_path.write_text("outside", encoding="utf-8")
    registry.save(
        AppManifest(
            app_id=manifest.app_id,
            name=manifest.name,
            backend=manifest.backend,
            source={**manifest.source, "managed_path": str(outside_path)},
            permissions=manifest.permissions,
            trust_tier=manifest.trust_tier,
            installed_at=manifest.installed_at,
        )
    )

    exit_code = main(["--registry-dir", str(registry_dir), "uninstall", "Example"])

    assert exit_code == 1
    assert registry.exists("Example")
    assert outside_path.exists()


def test_uninstall_appimage_outside_launcher_path_keeps_manifest_and_managed_file(tmp_path: Path) -> None:
    registry_dir = tmp_path / ".appresolver" / "apps"
    registry = AppRegistry(registry_dir)
    manifest = make_appimage_manifest(registry_dir, "Example")
    managed_path = Path(str(manifest.source["managed_path"]))
    managed_path.parent.mkdir(parents=True)
    managed_path.write_text("managed", encoding="utf-8")
    outside_launcher = tmp_path / "outside.desktop"
    outside_launcher.write_text("outside", encoding="utf-8")
    registry.save(
        AppManifest(
            app_id=manifest.app_id,
            name=manifest.name,
            backend=manifest.backend,
            source={**manifest.source, "launcher_path": str(outside_launcher)},
            permissions=manifest.permissions,
            trust_tier=manifest.trust_tier,
            installed_at=manifest.installed_at,
        )
    )

    exit_code = main(["--registry-dir", str(registry_dir), "uninstall", "Example"])

    assert exit_code == 1
    assert registry.exists("Example")
    assert managed_path.exists()
    assert outside_launcher.exists()


def test_define_environment_writes_manifest_with_defaults(tmp_path: Path, capsys: CaptureFixture[str]) -> None:
    registry_dir = tmp_path / ".appresolver" / "apps"
    state_paths = StatePaths.from_registry_dir(registry_dir)

    exit_code = main(
        [
            "--registry-dir",
            str(registry_dir),
            "define-environment",
            "ubuntu-24.04-default",
            "--name",
            "Ubuntu 24.04 Default",
            "--backend",
            "container",
            "--image",
            "ubuntu:24.04",
        ]
    )

    manifest = EnvironmentRegistry(state_paths.environments_dir).load("ubuntu-24.04-default")
    assert exit_code == 0
    assert manifest.environment_id == "ubuntu-24.04-default"
    assert manifest.name == "Ubuntu 24.04 Default"
    assert manifest.backend == "container"
    assert manifest.image == "ubuntu:24.04"
    assert manifest.status == "defined"
    assert manifest.source == {"type": "manual"}
    assert manifest.permissions == {}
    assert manifest.apps == []
    assert capsys.readouterr().out.startswith("Defined environment ubuntu-24.04-default\n")


def test_dry_run_define_environment_creates_no_environment_directory(
    tmp_path: Path, capsys: CaptureFixture[str]
) -> None:
    registry_dir = tmp_path / ".appresolver" / "apps"
    state_paths = StatePaths.from_registry_dir(registry_dir)

    exit_code = main(
        [
            "--registry-dir",
            str(registry_dir),
            "--dry-run",
            "define-environment",
            "ubuntu-24.04-default",
            "--name",
            "Ubuntu 24.04 Default",
            "--backend",
            "container",
            "--image",
            "ubuntu:24.04",
        ]
    )

    assert exit_code == 0
    assert not state_paths.environments_dir.exists()
    assert "Would write environment manifest:" in capsys.readouterr().out


def test_subcommand_dry_run_define_environment_creates_no_environment_directory(
    tmp_path: Path, capsys: CaptureFixture[str]
) -> None:
    registry_dir = tmp_path / ".appresolver" / "apps"
    state_paths = StatePaths.from_registry_dir(registry_dir)

    exit_code = main(
        [
            "--registry-dir",
            str(registry_dir),
            "define-environment",
            "ubuntu-24.04-default",
            "--name",
            "Ubuntu 24.04 Default",
            "--backend",
            "container",
            "--image",
            "ubuntu:24.04",
            "--dry-run",
        ]
    )

    assert exit_code == 0
    assert not state_paths.environments_dir.exists()
    assert "Would write environment manifest:" in capsys.readouterr().out


def test_define_environment_duplicate_does_not_overwrite_existing_manifest(tmp_path: Path) -> None:
    registry_dir = tmp_path / ".appresolver" / "apps"
    environment_registry = EnvironmentRegistry(StatePaths.from_registry_dir(registry_dir).environments_dir)
    main(
        [
            "--registry-dir",
            str(registry_dir),
            "define-environment",
            "ubuntu-24.04-default",
            "--name",
            "Original Name",
            "--backend",
            "container",
            "--image",
            "ubuntu:24.04",
        ]
    )

    exit_code = main(
        [
            "--registry-dir",
            str(registry_dir),
            "define-environment",
            "ubuntu-24.04-default",
            "--name",
            "New Name",
            "--backend",
            "container",
            "--image",
            "ubuntu:latest",
        ]
    )

    assert exit_code == 1
    assert environment_registry.load("ubuntu-24.04-default").name == "Original Name"


def test_list_environments_human_output_is_sorted(tmp_path: Path, capsys: CaptureFixture[str]) -> None:
    registry_dir = tmp_path / ".appresolver" / "apps"
    for environment_id in ["ubuntu-24.04-default", "fedora-latest", "arch-community"]:
        main(
            [
                "--registry-dir",
                str(registry_dir),
                "define-environment",
                environment_id,
                "--name",
                environment_id,
                "--backend",
                "container",
                "--image",
                "example:latest",
            ]
        )
        capsys.readouterr()

    exit_code = main(["--registry-dir", str(registry_dir), "list-environments"])

    assert exit_code == 0
    assert capsys.readouterr().out == "\n".join(
        [
            "arch-community\tcontainer\tdefined",
            "fedora-latest\tcontainer\tdefined",
            "ubuntu-24.04-default\tcontainer\tdefined",
            "",
        ]
    )


def test_list_environments_empty_human_output(tmp_path: Path, capsys: CaptureFixture[str]) -> None:
    registry_dir = tmp_path / ".appresolver" / "apps"

    exit_code = main(["--registry-dir", str(registry_dir), "list-environments"])

    assert exit_code == 0
    assert capsys.readouterr().out == "No resolver-managed environments.\n"


def test_list_environments_json_output(tmp_path: Path, capsys: CaptureFixture[str]) -> None:
    registry_dir = tmp_path / ".appresolver" / "apps"
    main(
        [
            "--registry-dir",
            str(registry_dir),
            "define-environment",
            "ubuntu-24.04-default",
            "--name",
            "Ubuntu 24.04 Default",
            "--backend",
            "container",
            "--image",
            "ubuntu:24.04",
        ]
    )
    capsys.readouterr()

    exit_code = main(["--registry-dir", str(registry_dir), "--json", "list-environments"])

    output = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert output[0]["environment_id"] == "ubuntu-24.04-default"
    assert output[0]["name"] == "Ubuntu 24.04 Default"
    assert output[0]["backend"] == "container"
    assert output[0]["image"] == "ubuntu:24.04"
    assert output[0]["status"] == "defined"
    assert "created_at" in output[0]


def test_subcommand_json_list_environments_output(tmp_path: Path, capsys: CaptureFixture[str]) -> None:
    registry_dir = tmp_path / ".appresolver" / "apps"

    exit_code = main(["--registry-dir", str(registry_dir), "list-environments", "--json"])

    assert exit_code == 0
    assert json.loads(capsys.readouterr().out) == []


def test_show_environment_human_output(tmp_path: Path, capsys: CaptureFixture[str]) -> None:
    registry_dir = tmp_path / ".appresolver" / "apps"
    main(
        [
            "--registry-dir",
            str(registry_dir),
            "define-environment",
            "ubuntu-24.04-default",
            "--name",
            "Ubuntu 24.04 Default",
            "--backend",
            "container",
            "--image",
            "ubuntu:24.04",
        ]
    )
    capsys.readouterr()

    exit_code = main(["--registry-dir", str(registry_dir), "show-environment", "ubuntu-24.04-default"])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert output.startswith("Environment ubuntu-24.04-default:\n")
    assert '"status": "defined"' in output
    assert '"source": {' in output


def test_show_environment_json_output(tmp_path: Path, capsys: CaptureFixture[str]) -> None:
    registry_dir = tmp_path / ".appresolver" / "apps"
    main(
        [
            "--registry-dir",
            str(registry_dir),
            "define-environment",
            "ubuntu-24.04-default",
            "--name",
            "Ubuntu 24.04 Default",
            "--backend",
            "container",
            "--image",
            "ubuntu:24.04",
        ]
    )
    capsys.readouterr()

    exit_code = main(["--registry-dir", str(registry_dir), "--json", "show-environment", "ubuntu-24.04-default"])

    output = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert output["environment_id"] == "ubuntu-24.04-default"
    assert output["source"] == {"type": "manual"}
    assert output["permissions"] == {}
    assert output["apps"] == []


def test_subcommand_json_show_environment_output(tmp_path: Path, capsys: CaptureFixture[str]) -> None:
    registry_dir = tmp_path / ".appresolver" / "apps"
    main(
        [
            "--registry-dir",
            str(registry_dir),
            "define-environment",
            "ubuntu-24.04-default",
            "--name",
            "Ubuntu 24.04 Default",
            "--backend",
            "container",
            "--image",
            "ubuntu:24.04",
        ]
    )
    capsys.readouterr()

    exit_code = main(["--registry-dir", str(registry_dir), "show-environment", "ubuntu-24.04-default", "--json"])

    output = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert output["environment_id"] == "ubuntu-24.04-default"


def test_delete_environment_removes_manifest(tmp_path: Path, capsys: CaptureFixture[str]) -> None:
    registry_dir = tmp_path / ".appresolver" / "apps"
    environment_registry = EnvironmentRegistry(StatePaths.from_registry_dir(registry_dir).environments_dir)
    main(
        [
            "--registry-dir",
            str(registry_dir),
            "define-environment",
            "ubuntu-24.04-default",
            "--name",
            "Ubuntu 24.04 Default",
            "--backend",
            "container",
            "--image",
            "ubuntu:24.04",
        ]
    )
    capsys.readouterr()

    exit_code = main(["--registry-dir", str(registry_dir), "delete-environment", "ubuntu-24.04-default"])

    assert exit_code == 0
    assert not environment_registry.exists("ubuntu-24.04-default")
    assert capsys.readouterr().out == "Deleted environment ubuntu-24.04-default\n"


def test_dry_run_delete_environment_does_not_delete_manifest(
    tmp_path: Path, capsys: CaptureFixture[str]
) -> None:
    registry_dir = tmp_path / ".appresolver" / "apps"
    environment_registry = EnvironmentRegistry(StatePaths.from_registry_dir(registry_dir).environments_dir)
    main(
        [
            "--registry-dir",
            str(registry_dir),
            "define-environment",
            "ubuntu-24.04-default",
            "--name",
            "Ubuntu 24.04 Default",
            "--backend",
            "container",
            "--image",
            "ubuntu:24.04",
        ]
    )
    capsys.readouterr()

    exit_code = main(["--registry-dir", str(registry_dir), "--dry-run", "delete-environment", "ubuntu-24.04-default"])

    assert exit_code == 0
    assert environment_registry.exists("ubuntu-24.04-default")
    assert "Would delete environment manifest:" in capsys.readouterr().out


def test_subcommand_dry_run_delete_environment_does_not_delete_manifest(
    tmp_path: Path, capsys: CaptureFixture[str]
) -> None:
    registry_dir = tmp_path / ".appresolver" / "apps"
    environment_registry = EnvironmentRegistry(StatePaths.from_registry_dir(registry_dir).environments_dir)
    main(
        [
            "--registry-dir",
            str(registry_dir),
            "define-environment",
            "ubuntu-24.04-default",
            "--name",
            "Ubuntu 24.04 Default",
            "--backend",
            "container",
            "--image",
            "ubuntu:24.04",
        ]
    )
    capsys.readouterr()

    exit_code = main(
        ["--registry-dir", str(registry_dir), "delete-environment", "ubuntu-24.04-default", "--dry-run"]
    )

    assert exit_code == 0
    assert environment_registry.exists("ubuntu-24.04-default")
    assert "Would delete environment manifest:" in capsys.readouterr().out


def test_show_environment_missing_exits_nonzero(tmp_path: Path) -> None:
    registry_dir = tmp_path / ".appresolver" / "apps"

    exit_code = main(["--registry-dir", str(registry_dir), "show-environment", "missing-env"])

    assert exit_code == 1


def test_delete_environment_missing_exits_nonzero(tmp_path: Path) -> None:
    registry_dir = tmp_path / ".appresolver" / "apps"

    exit_code = main(["--registry-dir", str(registry_dir), "delete-environment", "missing-env"])

    assert exit_code == 1


def test_define_environment_with_custom_registry_dir_uses_sibling_environments_dir(tmp_path: Path) -> None:
    registry_dir = tmp_path / "custom-state" / "apps"

    exit_code = main(
        [
            "--registry-dir",
            str(registry_dir),
            "define-environment",
            "ubuntu-24.04-default",
            "--name",
            "Ubuntu 24.04 Default",
            "--backend",
            "container",
            "--image",
            "ubuntu:24.04",
        ]
    )

    assert exit_code == 0
    assert (tmp_path / "custom-state" / "environments" / "ubuntu-24.04-default.json").exists()
    assert not (tmp_path / ".appresolver").exists()
