from __future__ import annotations

import json
from typing import Any


def format_command(command: list[str]) -> str:
    return " ".join(command)


def format_actions(actions: list[dict[str, Any]]) -> str:
    if not actions:
        return "No planned actions."
    return "\n".join(format_command(action["command"]) for action in actions if isinstance(action.get("command"), list))


def format_packages(packages: list[dict[str, str]]) -> str:
    if not packages:
        return "No resolver-tracked packages."
    return "\n".join(f"{package['name']}\t{package['manager']}\t{package['installed_at']}" for package in packages)


def format_app_row(summary: dict[str, object]) -> str:
    name = str(summary.get("name") or summary.get("app_id") or "unknown")
    app_id = str(summary.get("app_id") or name)
    backend = str(summary.get("backend") or "unknown")
    if name == app_id:
        return f"{name}\t{backend}"
    return f"{name} ({app_id})\t{backend}"


def format_app_details(summary: dict[str, object]) -> str:
    lines = [
        f"Name: {summary.get('name', '')}",
        f"App ID: {summary.get('app_id', '')}",
        f"Type: {summary.get('backend', '')}",
        f"Status: {summary.get('status', '')}",
        f"Trust tier: {summary.get('trust_tier', '')}",
        f"Permissions: {summary.get('permissions_summary', '')}",
        f"Source: {summary.get('source_summary', '')}",
        f"Manifest: {summary.get('manifest_path', '')}",
    ]
    source_details = summary.get("source_details")
    if isinstance(source_details, dict) and source_details:
        lines.append("Source details:")
        for key, value in source_details.items():
            lines.append(f"{key}: {value}")
    return "\n".join(lines)


def format_result(value: Any) -> str:
    if isinstance(value, dict):
        lines: list[str] = []
        for key, item in value.items():
            if key == "actions" and isinstance(item, list):
                lines.append("actions:")
                lines.append(format_actions(item))
            elif key == "tracked_packages" and isinstance(item, list):
                lines.append("tracked_packages:")
                lines.append(format_packages(item))
            elif key == "available_actions" and isinstance(item, list):
                lines.append("available_actions:")
                lines.extend(str(action) for action in item)
            else:
                lines.append(f"{key}: {format_scalar(item)}")
        return "\n".join(lines)
    if isinstance(value, list):
        return json.dumps(value, indent=2, sort_keys=True)
    return str(value)


def format_error(error: BaseException) -> str:
    return f"error: {error}"


def format_scalar(value: Any) -> str:
    if isinstance(value, (dict, list)):
        return json.dumps(value, indent=2, sort_keys=True)
    return str(value)
