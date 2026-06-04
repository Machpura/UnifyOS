from __future__ import annotations

import argparse
import sys
from pathlib import Path

from appresolver.registry import default_registry_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="appresolver-gui", description="Experimental App Resolver GUI")
    parser.add_argument(
        "--registry-dir",
        type=Path,
        default=default_registry_dir(),
        help="registry directory; defaults to ./.appresolver/apps/ relative to the current working directory",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        from appresolver.gui.app import run_gui
    except ModuleNotFoundError as exc:
        if exc.name == "PySide6":
            print(
                "error: App Resolver GUI requires PySide6. "
                "Install it with: python -m pip install -e ./appresolver[gui]",
                file=sys.stderr,
            )
            return 1
        raise

    return run_gui(args.registry_dir)


if __name__ == "__main__":
    raise SystemExit(main())
