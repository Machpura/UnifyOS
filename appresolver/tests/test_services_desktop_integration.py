from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from appresolver.errors import AppResolverError, CommandExecutionError
from appresolver.services import desktop_integration


def set_data_home(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    data_home = tmp_path / "data home"
    monkeypatch.setenv("XDG_DATA_HOME", str(data_home))
    return data_home


def test_install_plan_mutates_nothing(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    data_home = set_data_home(monkeypatch, tmp_path)

    result = desktop_integration.install_desktop_integration(execute=False)

    assert result["status"] == "planned-install"
    assert result["executed"] is False
    assert result["files_to_write"] == [
        str(data_home / "applications" / "appresolver-open.desktop"),
        str(data_home / "mime" / "packages" / "appresolver-open.xml"),
    ]
    assert result["commands_to_run"] == [
        ["update-mime-database", str(data_home / "mime")],
        ["update-desktop-database", str(data_home / "applications")],
    ]
    assert not data_home.exists()


def test_install_execute_writes_desktop_file_and_mime_xml(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    data_home = set_data_home(monkeypatch, tmp_path)
    calls: list[list[str]] = []
    monkeypatch.setattr(desktop_integration.shutil, "which", lambda name: f"/usr/bin/{name}")

    def fake_run_command(command: list[str]) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        return subprocess.CompletedProcess(args=command, returncode=0, stdout="", stderr="")

    monkeypatch.setattr(desktop_integration.subprocess_runner, "run_command", fake_run_command)

    result = desktop_integration.install_desktop_integration(execute=True)

    desktop_file = data_home / "applications" / "appresolver-open.desktop"
    mime_file = data_home / "mime" / "packages" / "appresolver-open.xml"
    assert result["status"] == "installed"
    assert result["executed"] is True
    assert result["files_written"] == [str(desktop_file), str(mime_file)]
    assert result["commands_run"] == calls
    assert result["warnings"] == []
    assert desktop_file.read_text(encoding="utf-8") == desktop_integration.desktop_file_contents()
    assert mime_file.read_text(encoding="utf-8") == desktop_integration.mime_xml_contents()
    assert "MimeType=application/x-appimage;application/vnd.debian.binary-package;" in desktop_file.read_text(
        encoding="utf-8"
    )
    assert '<glob pattern="*.AppImage"/>' in mime_file.read_text(encoding="utf-8")
    assert '<glob pattern="*.flatpakref"/>' in mime_file.read_text(encoding="utf-8")


def test_remove_plan_mutates_nothing(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    data_home = set_data_home(monkeypatch, tmp_path)
    desktop_file = data_home / "applications" / "appresolver-open.desktop"
    desktop_file.parent.mkdir(parents=True)
    desktop_file.write_text(desktop_integration.desktop_file_contents(), encoding="utf-8")

    result = desktop_integration.remove_desktop_integration(execute=False)

    assert result["status"] == "planned-remove"
    assert result["executed"] is False
    assert result["files_to_remove"] == [
        str(desktop_file),
        str(data_home / "mime" / "packages" / "appresolver-open.xml"),
    ]
    assert desktop_file.exists()


def test_remove_execute_removes_only_generated_files(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    data_home = set_data_home(monkeypatch, tmp_path)
    desktop_file = data_home / "applications" / "appresolver-open.desktop"
    mime_file = data_home / "mime" / "packages" / "appresolver-open.xml"
    unrelated_file = data_home / "applications" / "other.desktop"
    desktop_file.parent.mkdir(parents=True)
    mime_file.parent.mkdir(parents=True)
    desktop_file.write_text(desktop_integration.desktop_file_contents(), encoding="utf-8")
    mime_file.write_text(desktop_integration.mime_xml_contents(), encoding="utf-8")
    unrelated_file.write_text("unrelated", encoding="utf-8")
    monkeypatch.setattr(desktop_integration.shutil, "which", lambda name: None)

    result = desktop_integration.remove_desktop_integration(execute=True)

    assert result["status"] == "removed"
    assert result["executed"] is True
    assert result["files_removed"] == [str(desktop_file), str(mime_file)]
    assert not desktop_file.exists()
    assert not mime_file.exists()
    assert unrelated_file.exists()


def test_remove_execute_tolerates_missing_files(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    set_data_home(monkeypatch, tmp_path)
    monkeypatch.setattr(desktop_integration.shutil, "which", lambda name: None)

    result = desktop_integration.remove_desktop_integration(execute=True)

    assert result["files_removed"] == []
    assert len(result["warnings"]) == 2


def test_install_refuses_to_overwrite_non_appresolver_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    data_home = set_data_home(monkeypatch, tmp_path)
    desktop_file = data_home / "applications" / "appresolver-open.desktop"
    desktop_file.parent.mkdir(parents=True)
    desktop_file.write_text("[Desktop Entry]\nName=Other\n", encoding="utf-8")

    with pytest.raises(AppResolverError, match="refusing to overwrite non-App Resolver file"):
        desktop_integration.install_desktop_integration(execute=True)

    assert desktop_file.read_text(encoding="utf-8") == "[Desktop Entry]\nName=Other\n"


def test_install_refuses_symlink_target(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    data_home = set_data_home(monkeypatch, tmp_path)
    outside_file = tmp_path / "outside.desktop"
    outside_file.write_text(desktop_integration.desktop_file_contents(), encoding="utf-8")
    desktop_file = data_home / "applications" / "appresolver-open.desktop"
    desktop_file.parent.mkdir(parents=True)
    desktop_file.symlink_to(outside_file)

    with pytest.raises(AppResolverError, match="refusing to overwrite symlink"):
        desktop_integration.install_desktop_integration(execute=True)

    assert outside_file.read_text(encoding="utf-8") == desktop_integration.desktop_file_contents()


def test_install_replaces_existing_appresolver_generated_files(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    data_home = set_data_home(monkeypatch, tmp_path)
    desktop_file = data_home / "applications" / "appresolver-open.desktop"
    mime_file = data_home / "mime" / "packages" / "appresolver-open.xml"
    desktop_file.parent.mkdir(parents=True)
    mime_file.parent.mkdir(parents=True)
    desktop_file.write_text("old\nX-AppResolver-Generated=true\n", encoding="utf-8")
    mime_file.write_text("<!-- AppResolver-Generated=true -->\nold\n", encoding="utf-8")
    monkeypatch.setattr(desktop_integration.shutil, "which", lambda name: None)

    desktop_integration.install_desktop_integration(execute=True)

    assert desktop_file.read_text(encoding="utf-8") == desktop_integration.desktop_file_contents()
    assert mime_file.read_text(encoding="utf-8") == desktop_integration.mime_xml_contents()


def test_remove_refuses_to_remove_non_appresolver_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    data_home = set_data_home(monkeypatch, tmp_path)
    desktop_file = data_home / "applications" / "appresolver-open.desktop"
    desktop_file.parent.mkdir(parents=True)
    desktop_file.write_text("[Desktop Entry]\nName=Other\n", encoding="utf-8")

    with pytest.raises(AppResolverError, match="refusing to remove non-App Resolver file"):
        desktop_integration.remove_desktop_integration(execute=True)

    assert desktop_file.exists()


def test_remove_refuses_symlink_target(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    data_home = set_data_home(monkeypatch, tmp_path)
    outside_file = tmp_path / "outside.desktop"
    outside_file.write_text(desktop_integration.desktop_file_contents(), encoding="utf-8")
    desktop_file = data_home / "applications" / "appresolver-open.desktop"
    desktop_file.parent.mkdir(parents=True)
    desktop_file.symlink_to(outside_file)

    with pytest.raises(AppResolverError, match="refusing to remove symlink"):
        desktop_integration.remove_desktop_integration(execute=True)

    assert desktop_file.exists()
    assert outside_file.exists()


def test_missing_update_commands_warn_without_crashing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    set_data_home(monkeypatch, tmp_path)
    monkeypatch.setattr(desktop_integration.shutil, "which", lambda name: None)

    result = desktop_integration.install_desktop_integration(execute=True)

    assert result["commands_run"] == []
    assert result["warnings"] == [
        "update-mime-database is not available; desktop integration cache was not refreshed",
        "update-desktop-database is not available; desktop integration cache was not refreshed",
    ]


def test_failing_update_commands_warn_without_crashing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    set_data_home(monkeypatch, tmp_path)
    monkeypatch.setattr(desktop_integration.shutil, "which", lambda name: f"/usr/bin/{name}")

    def fake_run_command(command: list[str]) -> subprocess.CompletedProcess[str]:
        raise CommandExecutionError(f"command failed: {' '.join(command)}")

    monkeypatch.setattr(desktop_integration.subprocess_runner, "run_command", fake_run_command)

    result = desktop_integration.install_desktop_integration(execute=True)

    assert result["commands_run"] == []
    assert result["warnings"] == [
        "command failed: update-mime-database " + str(tmp_path / "data home" / "mime"),
        "command failed: update-desktop-database " + str(tmp_path / "data home" / "applications"),
    ]
