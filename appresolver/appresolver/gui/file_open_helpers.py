from __future__ import annotations

from pathlib import Path
from typing import Any

from appresolver.registry import AppRegistry
from appresolver.services import files
from appresolver.state import StatePaths


def plan_file_open(registry: AppRegistry, state_paths: StatePaths, path: Path) -> dict[str, Any]:
    return files.open_path(registry, state_paths, path, execute=False)


def execute_file_open(registry: AppRegistry, state_paths: StatePaths, path: Path) -> dict[str, Any]:
    return files.open_path(registry, state_paths, path, execute=True)


def build_file_open_view(result: dict[str, Any]) -> dict[str, Any]:
    full_path = str(result["path"])
    detected_type = str(result["detected_type"])
    supported = bool(result["supported"])
    can_execute = detected_type == "appimage" and supported
    type_label = type_label_for_detected_type(detected_type)
    return {
        "title": title_for_result(Path(full_path).name, type_label, can_execute),
        "file_name": Path(full_path).name,
        "full_path": full_path,
        "detected_type": detected_type,
        "type_label": type_label,
        "route": str(result["route"]),
        "method_label": method_label_for_result(result),
        "supported": supported,
        "supported_text": "yes" if supported else "no",
        "status": str(result["status"]),
        "message": str(result["message"]),
        "short_message": short_message_for_result(result),
        "safety_notes": safety_notes_for_result(result),
        "planned_actions": format_file_actions(result.get("actions")),
        "can_execute": can_execute,
        "action_label": "Import" if can_execute else "",
        "details_available": True,
        "details_collapsed": True,
        "raw_result": result,
    }


def build_file_open_success_view(result: dict[str, Any]) -> dict[str, Any]:
    app_id = str(result.get("app_id", "app"))
    return {
        "title": f"{app_id} was imported successfully.",
        "app_id": app_id,
        "status": "imported",
        "success_message": f"{app_id} was imported successfully.",
        "can_execute": False,
        "action_label": "",
        "close_available": True,
        "details_available": True,
        "details_collapsed": True,
        "details": imported_app_details(result),
        "raw_result": result,
    }


def type_label_for_detected_type(detected_type: str) -> str:
    labels = {
        "appimage": "AppImage",
        "deb": "Debian package",
        "rpm": "RPM package",
        "windows-installer": "Windows installer",
        "flatpakref": "Flatpak ref",
        "shell-script": "Shell script",
        "unknown": "Unknown file",
    }
    return labels.get(detected_type, detected_type)


def title_for_result(file_name: str, type_label: str, can_execute: bool) -> str:
    if can_execute:
        return f"Install {file_name}?"
    return f"Open {file_name}?"


def method_label_for_result(result: dict[str, Any]) -> str:
    detected_type = str(result["detected_type"])
    if detected_type == "appimage":
        return "Managed AppImage import"
    if detected_type == "deb":
        return "Future Debian/Ubuntu compatibility environment"
    if detected_type == "rpm":
        return "Future Fedora/RPM compatibility environment"
    if detected_type == "windows-installer":
        return "Future Windows compatibility/Wine environment"
    if detected_type == "flatpakref":
        return "Flatpak ref support not implemented yet"
    if detected_type == "shell-script":
        return "Owner Mode-only future work"
    return "Unsupported file type"


def short_message_for_result(result: dict[str, Any]) -> str:
    detected_type = str(result["detected_type"])
    if detected_type == "appimage":
        return "App Resolver will import this file without running it during install."
    if detected_type == "deb":
        return "Debian package import is not implemented yet. Future route: Debian/Ubuntu compatibility environment."
    if detected_type == "rpm":
        return "RPM package import is not implemented yet. Future route: Fedora/RPM compatibility environment."
    if detected_type == "windows-installer":
        return "Windows installer support is not implemented yet. Future route: Windows compatibility/Wine environment."
    if detected_type == "flatpakref":
        return "Flatpak ref support is not implemented yet."
    if detected_type == "shell-script":
        return "Shell scripts are refused in normal mode and are Owner Mode-only future work."
    return "Unsupported file type."


def safety_notes_for_result(result: dict[str, Any]) -> list[str]:
    detected_type = str(result["detected_type"])
    if detected_type == "appimage":
        return [
            "App Resolver will copy this AppImage into resolver-managed state.",
            "The AppImage will not be executed during import.",
        ]
    if detected_type == "shell-script":
        return ["Shell scripts are refused in normal mode and are Owner Mode-only future work."]
    if detected_type in {"deb", "rpm", "windows-installer", "flatpakref"}:
        return ["This file type is detected for planning only in this prototype."]
    return ["This file type is not supported by App Resolver yet."]


def format_file_actions(actions: object) -> list[str]:
    if not isinstance(actions, list):
        return []

    formatted: list[str] = []
    for action in actions:
        if not isinstance(action, dict):
            continue
        formatted.append(format_file_action(action))
    return formatted


def format_file_action(action: dict[str, object]) -> str:
    description = str(action.get("description", action.get("id", "action")))
    if "source" in action and "target" in action:
        return f"{description}: {action['source']} -> {action['target']}"
    if "path" in action:
        return f"{description}: {action['path']}"
    if isinstance(action.get("command"), list):
        return " ".join(str(part) for part in action["command"])
    return description


def imported_app_details(result: dict[str, Any]) -> list[str]:
    details: list[str] = []
    app_id = result.get("app_id")
    if app_id is not None:
        details.append(f"Imported app ID: {app_id}")
    for action in result.get("actions", []):
        if not isinstance(action, dict):
            continue
        action_id = action.get("id")
        if action_id == "chmod-appimage" and "path" in action:
            details.append(f"Managed AppImage: {action['path']}")
        elif action_id == "write-manifest" and "path" in action:
            details.append(f"Manifest: {action['path']}")
    return details
