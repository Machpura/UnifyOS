from __future__ import annotations

from appresolver.gui.helpers import (
    format_actions,
    format_app_details,
    format_app_row,
    format_error,
    format_packages,
    format_result,
)


def test_format_actions_outputs_command_lines() -> None:
    output = format_actions(
        [
            {
                "id": "start-container",
                "description": "Start managed environment container",
                "command": ["podman", "start", "appresolver-env-ubuntu-24.04-default"],
            },
            {
                "id": "apt-install",
                "description": "Install package with apt",
                "command": ["podman", "exec", "env", "apt-get", "install", "-y", "curl"],
            },
        ]
    )

    assert output == "\n".join(
        [
            "podman start appresolver-env-ubuntu-24.04-default",
            "podman exec env apt-get install -y curl",
        ]
    )


def test_format_actions_empty_output() -> None:
    assert format_actions([]) == "No planned actions."


def test_format_packages_outputs_tracked_packages() -> None:
    output = format_packages(
        [{"name": "curl", "manager": "apt", "installed_at": "2026-06-03T12:00:00+00:00"}]
    )

    assert output == "curl\tapt\t2026-06-03T12:00:00+00:00"


def test_format_packages_empty_output() -> None:
    assert format_packages([]) == "No resolver-tracked packages."


def test_format_app_row_outputs_name_id_and_backend() -> None:
    assert (
        format_app_row({"name": "Example", "app_id": "Example", "backend": "appimage"})
        == "Example\tappimage"
    )
    assert (
        format_app_row({"name": "Example App", "app_id": "com.example.App", "backend": "flatpak"})
        == "Example App (com.example.App)\tflatpak"
    )


def test_format_app_details_outputs_summary_fields() -> None:
    output = format_app_details(
        {
            "name": "Example",
            "app_id": "Example",
            "backend": "appimage",
            "status": "installed",
            "trust_tier": "unverified",
            "permissions_summary": "sandboxed: False",
            "source_summary": "Managed AppImage: Example.AppImage",
            "manifest_path": "/state/apps/Example.json",
            "source_details": {
                "managed_path": "/state/appimages/Example.AppImage",
                "launcher_path": "/state/launchers/Example.desktop",
            },
        }
    )

    assert "Name: Example" in output
    assert "Type: appimage" in output
    assert "Status: installed" in output
    assert "managed_path: /state/appimages/Example.AppImage" in output


def test_format_result_includes_actions_packages_and_available_actions() -> None:
    output = format_result(
        {
            "environment_id": "ubuntu-24.04-default",
            "tracked_packages": [
                {"name": "curl", "manager": "apt", "installed_at": "2026-06-03T12:00:00+00:00"}
            ],
            "available_actions": ["stop-environment", "install-package"],
            "actions": [
                {
                    "id": "stop-container",
                    "description": "Stop managed environment container",
                    "command": ["podman", "stop", "appresolver-env-ubuntu-24.04-default"],
                }
            ],
        }
    )

    assert "environment_id: ubuntu-24.04-default" in output
    assert "curl\tapt\t2026-06-03T12:00:00+00:00" in output
    assert "stop-environment" in output
    assert "podman stop appresolver-env-ubuntu-24.04-default" in output


def test_format_error() -> None:
    assert format_error(ValueError("missing environment")) == "error: missing environment"
