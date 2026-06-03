from __future__ import annotations

import subprocess
from typing import Any

import pytest

from appresolver.backends import flatpak
from appresolver.errors import CommandExecutionError


def completed(stdout: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=["flatpak"], returncode=0, stdout=stdout, stderr="")


def test_install_flatpak_runs_install_then_permission_inspection(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[list[str]] = []

    def fake_run_command(command: list[str]) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        if command == ["flatpak", "info", "--show-permissions", "com.example.App"]:
            return completed("[Context]\nshared=network;ipc;\n")
        return completed()

    monkeypatch.setattr(flatpak, "require_flatpak", lambda: None)
    monkeypatch.setattr(flatpak, "run_command", fake_run_command)

    manifest = flatpak.install_flatpak("com.example.App")

    assert calls == [
        ["flatpak", "install", "-y", "flathub", "com.example.App"],
        ["flatpak", "info", "--show-permissions", "com.example.App"],
    ]
    assert manifest.app_id == "com.example.App"
    assert manifest.backend == "flatpak"
    assert manifest.permissions["flatpak"]["Context"]["shared"] == "network;ipc;"


def test_install_flatpak_raises_when_install_command_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[list[str]] = []

    def fake_run_command(command: list[str]) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        raise CommandExecutionError("install failed")

    monkeypatch.setattr(flatpak, "require_flatpak", lambda: None)
    monkeypatch.setattr(flatpak, "run_command", fake_run_command)

    with pytest.raises(CommandExecutionError, match="install failed"):
        flatpak.install_flatpak("com.example.App")

    assert calls == [["flatpak", "install", "-y", "flathub", "com.example.App"]]


def test_install_flatpak_raises_when_permission_inspection_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[list[str]] = []

    def fake_run_command(command: list[str]) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        if command == ["flatpak", "info", "--show-permissions", "com.example.App"]:
            raise CommandExecutionError("permissions failed")
        return completed()

    monkeypatch.setattr(flatpak, "require_flatpak", lambda: None)
    monkeypatch.setattr(flatpak, "run_command", fake_run_command)

    with pytest.raises(CommandExecutionError, match="permissions failed"):
        flatpak.install_flatpak("com.example.App")

    assert calls == [
        ["flatpak", "install", "-y", "flathub", "com.example.App"],
        ["flatpak", "info", "--show-permissions", "com.example.App"],
    ]
    assert ["flatpak", "uninstall", "-y", "com.example.App"] not in calls


def test_uninstall_flatpak_runs_uninstall_command(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[list[str]] = []

    def fake_run_command(command: list[str]) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        return completed()

    monkeypatch.setattr(flatpak, "require_flatpak", lambda: None)
    monkeypatch.setattr(flatpak, "run_command", fake_run_command)

    flatpak.uninstall_flatpak("com.example.App")

    assert calls == [["flatpak", "uninstall", "-y", "com.example.App"]]


def test_uninstall_flatpak_raises_when_uninstall_command_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run_command(command: list[str]) -> subprocess.CompletedProcess[str]:
        raise CommandExecutionError(f"failed: {' '.join(command)}")

    monkeypatch.setattr(flatpak, "require_flatpak", lambda: None)
    monkeypatch.setattr(flatpak, "run_command", fake_run_command)

    with pytest.raises(CommandExecutionError, match="flatpak uninstall -y com.example.App"):
        flatpak.uninstall_flatpak("com.example.App")


def test_parse_flatpak_permissions_with_sample_output() -> None:
    sample_output = """
[Context]
shared=network;ipc;
sockets=x11;wayland;pulseaudio;
devices=dri;
filesystems=xdg-download;home:ro;

[Session Bus Policy]
org.freedesktop.Notifications=talk

[Environment]
FOO=bar=baz

[System Bus Policy]
org.freedesktop.Avahi=talk
"""

    permissions: dict[str, Any] = flatpak.parse_flatpak_permissions(sample_output)

    assert permissions == {
        "flatpak": {
            "raw": {},
            "Context": {
                "shared": "network;ipc;",
                "sockets": "x11;wayland;pulseaudio;",
                "devices": "dri;",
                "filesystems": "xdg-download;home:ro;",
            },
            "Session Bus Policy": {"org.freedesktop.Notifications": "talk"},
            "Environment": {"FOO": "bar=baz"},
            "System Bus Policy": {"org.freedesktop.Avahi": "talk"},
        }
    }

