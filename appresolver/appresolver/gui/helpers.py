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
