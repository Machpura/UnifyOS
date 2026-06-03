from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from pytest import CaptureFixture

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
