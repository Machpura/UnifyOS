from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Any

from appresolver import subprocess_runner
from appresolver.errors import AppResolverError, CommandExecutionError


DESKTOP_FILENAME = "appresolver-open.desktop"
MIME_FILENAME = "appresolver-open.xml"
DESKTOP_MARKER = "X-AppResolver-Generated=true"
XML_MARKER = "AppResolver-Generated=true"
MIME_TYPES = [
    "application/x-appimage",
    "application/vnd.debian.binary-package",
    "application/x-rpm",
    "application/x-msdownload",
    "application/x-shellscript",
    "application/vnd.flatpak.ref",
]


def install_desktop_integration(execute: bool) -> dict[str, Any]:
    paths = integration_paths()
    commands = update_commands(paths)
    if not execute:
        return {
            "status": "planned-install",
            "executed": False,
            "files_to_write": [str(paths["desktop_file"]), str(paths["mime_file"])],
            "commands_to_run": commands,
        }

    ensure_safe_install_target(paths["desktop_file"], DESKTOP_MARKER)
    ensure_safe_install_target(paths["mime_file"], XML_MARKER)
    paths["desktop_file"].parent.mkdir(parents=True, exist_ok=True)
    paths["mime_file"].parent.mkdir(parents=True, exist_ok=True)
    paths["desktop_file"].write_text(desktop_file_contents(), encoding="utf-8")
    paths["mime_file"].write_text(mime_xml_contents(), encoding="utf-8")
    commands_run, warnings = run_update_commands(commands)
    return {
        "status": "installed",
        "executed": True,
        "files_written": [str(paths["desktop_file"]), str(paths["mime_file"])],
        "commands_run": commands_run,
        "warnings": warnings,
    }


def remove_desktop_integration(execute: bool) -> dict[str, Any]:
    paths = integration_paths()
    commands = update_commands(paths)
    if not execute:
        return {
            "status": "planned-remove",
            "executed": False,
            "files_to_remove": [str(paths["desktop_file"]), str(paths["mime_file"])],
            "commands_to_run": commands,
        }

    files_removed: list[str] = []
    remove_generated_file(paths["desktop_file"], DESKTOP_MARKER, files_removed)
    remove_generated_file(paths["mime_file"], XML_MARKER, files_removed)
    commands_run, warnings = run_update_commands(commands)
    return {
        "status": "removed",
        "executed": True,
        "files_removed": files_removed,
        "commands_run": commands_run,
        "warnings": warnings,
    }


def integration_paths() -> dict[str, Path]:
    data_home = data_home_path()
    return {
        "data_home": data_home,
        "applications_dir": data_home / "applications",
        "mime_dir": data_home / "mime",
        "desktop_file": data_home / "applications" / DESKTOP_FILENAME,
        "mime_file": data_home / "mime" / "packages" / MIME_FILENAME,
    }


def data_home_path() -> Path:
    value = os.environ.get("XDG_DATA_HOME")
    if value:
        return Path(value).expanduser()
    return Path.home() / ".local" / "share"


def update_commands(paths: dict[str, Path]) -> list[list[str]]:
    return [
        ["update-mime-database", str(paths["mime_dir"])],
        ["update-desktop-database", str(paths["applications_dir"])],
    ]


def desktop_file_contents() -> str:
    return "\n".join(
        [
            "[Desktop Entry]",
            "Name=App Resolver",
            "Comment=Open files with App Resolver",
            "Exec=appresolver-gui --open %f",
            "Terminal=false",
            "Type=Application",
            "Categories=Utility;",
            f"MimeType={';'.join(MIME_TYPES)};",
            DESKTOP_MARKER,
            "",
        ]
    )


def mime_xml_contents() -> str:
    return "\n".join(
        [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<mime-info xmlns="http://www.freedesktop.org/standards/shared-mime-info">',
            f"  <!-- {XML_MARKER} -->",
            '  <mime-type type="application/x-appimage">',
            "    <comment>AppImage application</comment>",
            '    <glob pattern="*.AppImage"/>',
            '    <glob pattern="*.appimage"/>',
            "  </mime-type>",
            '  <mime-type type="application/vnd.debian.binary-package">',
            "    <comment>Debian package</comment>",
            '    <glob pattern="*.deb"/>',
            "  </mime-type>",
            '  <mime-type type="application/x-rpm">',
            "    <comment>RPM package</comment>",
            '    <glob pattern="*.rpm"/>',
            "  </mime-type>",
            '  <mime-type type="application/x-msdownload">',
            "    <comment>Windows executable</comment>",
            '    <glob pattern="*.exe"/>',
            "  </mime-type>",
            '  <mime-type type="application/x-shellscript">',
            "    <comment>Shell script</comment>",
            '    <glob pattern="*.sh"/>',
            "  </mime-type>",
            '  <mime-type type="application/vnd.flatpak.ref">',
            "    <comment>Flatpak reference</comment>",
            '    <glob pattern="*.flatpakref"/>',
            "  </mime-type>",
            "</mime-info>",
            "",
        ]
    )


def ensure_safe_install_target(path: Path, marker: str) -> None:
    if path.is_symlink():
        raise AppResolverError(f"refusing to overwrite symlink desktop integration target: {path}")
    if not path.exists():
        return
    if not path.is_file():
        raise AppResolverError(f"refusing to overwrite non-file desktop integration target: {path}")
    try:
        content = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise AppResolverError(f"failed to inspect existing desktop integration target {path}: {exc}") from exc
    if marker not in content:
        raise AppResolverError(f"refusing to overwrite non-App Resolver file: {path}")


def remove_generated_file(path: Path, marker: str, files_removed: list[str]) -> None:
    if path.is_symlink():
        raise AppResolverError(f"refusing to remove symlink desktop integration target: {path}")
    if not path.exists():
        return
    if not path.is_file():
        raise AppResolverError(f"refusing to remove non-file desktop integration target: {path}")
    try:
        content = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise AppResolverError(f"failed to inspect existing desktop integration target {path}: {exc}") from exc
    if marker not in content:
        raise AppResolverError(f"refusing to remove non-App Resolver file: {path}")

    try:
        path.unlink()
    except OSError as exc:
        raise AppResolverError(f"failed to remove desktop integration file {path}: {exc}") from exc
    files_removed.append(str(path))


def run_update_commands(commands: list[list[str]]) -> tuple[list[list[str]], list[str]]:
    commands_run: list[list[str]] = []
    warnings: list[str] = []
    for command in commands:
        executable = command[0]
        if shutil.which(executable) is None:
            warnings.append(f"{executable} is not available; desktop integration cache was not refreshed")
            continue
        try:
            subprocess_runner.run_command(command)
        except CommandExecutionError as exc:
            warnings.append(str(exc))
            continue
        commands_run.append(command)
    return commands_run, warnings
