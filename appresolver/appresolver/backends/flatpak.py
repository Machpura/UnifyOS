from __future__ import annotations

import shutil

from appresolver.errors import BackendError
from appresolver.manifest import AppManifest, utc_timestamp
from appresolver.registry import validate_app_id
from appresolver.subprocess_runner import run_command


def require_flatpak() -> None:
    if shutil.which("flatpak") is None:
        raise BackendError("flatpak is not installed or is not available on PATH")


def install_flatpak(app_id: str) -> AppManifest:
    validate_app_id(app_id)
    require_flatpak()
    run_command(["flatpak", "install", "-y", "flathub", app_id])
    permissions = read_flatpak_permissions(app_id)
    return AppManifest(
        app_id=app_id,
        name=app_id,
        backend="flatpak",
        source={"type": "flatpak", "remote": "flathub", "app_id": app_id},
        permissions=permissions,
        trust_tier="community",
        installed_at=utc_timestamp(),
    )


def read_flatpak_permissions(app_id: str) -> dict[str, object]:
    validate_app_id(app_id)
    require_flatpak()
    result = run_command(["flatpak", "info", "--show-permissions", app_id])
    return parse_flatpak_permissions(result.stdout)


def uninstall_flatpak(app_id: str) -> None:
    validate_app_id(app_id)
    require_flatpak()
    run_command(["flatpak", "uninstall", "-y", app_id])


def parse_flatpak_permissions(output: str) -> dict[str, object]:
    sections: dict[str, dict[str, str]] = {}
    current_section = "raw"
    sections[current_section] = {}

    for raw_line in output.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("[") and line.endswith("]"):
            current_section = line[1:-1]
            sections.setdefault(current_section, {})
            continue
        if "=" in line:
            key, value = line.split("=", 1)
            sections.setdefault(current_section, {})[key.strip()] = value.strip()
        else:
            sections.setdefault(current_section, {})[line] = "true"

    return {"flatpak": sections}

