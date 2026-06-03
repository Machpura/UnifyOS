from __future__ import annotations

import subprocess

from appresolver.errors import CommandExecutionError


def run_command(command: list[str]) -> subprocess.CompletedProcess[str]:
    try:
        result = subprocess.run(command, check=False, capture_output=True, text=True)
    except OSError as exc:
        raise CommandExecutionError(f"failed to run {' '.join(command)}: {exc}") from exc

    if result.returncode != 0:
        stderr = result.stderr.strip()
        detail = f": {stderr}" if stderr else ""
        raise CommandExecutionError(f"command failed ({result.returncode}): {' '.join(command)}{detail}")

    return result

