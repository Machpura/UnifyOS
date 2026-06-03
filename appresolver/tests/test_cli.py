from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from pytest import CaptureFixture

from appresolver.backends.appimage import launcher_path, managed_appimage_path
from appresolver.backends import flatpak
from appresolver.cli import main
from appresolver.errors import CommandExecutionError
from appresolver.manifest import AppManifest
from appresolver.registry import AppRegistry


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


def test_dry_run_import_appimage_mutates_nothing(tmp_path: Path, capsys: CaptureFixture[str]) -> None:
    registry_dir = tmp_path / ".appresolver" / "apps"
    source_path = write_appimage(tmp_path / "downloads" / "Example.AppImage")

    exit_code = main(["--registry-dir", str(registry_dir), "--dry-run", "import-appimage", str(source_path)])

    assert exit_code == 0
    assert not registry_dir.exists()
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
