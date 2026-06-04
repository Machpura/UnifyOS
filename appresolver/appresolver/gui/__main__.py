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
    parser.add_argument(
        "--open",
        dest="open_path",
        type=Path,
        help="open a focused App Resolver dialog for one file",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.open_path is not None:
            return run_file_open_gui_entry(args.registry_dir, args.open_path)
        return run_manager_gui(args.registry_dir)
    except ModuleNotFoundError as exc:
        if exc.name == "PySide6":
            print(
                "error: App Resolver GUI requires PySide6. "
                "Install it with: python -m pip install -e ./appresolver[gui]",
                file=sys.stderr,
            )
            return 1
        raise


def run_manager_gui(registry_dir: Path) -> int:
    from appresolver.gui.app import run_gui

    return run_gui(registry_dir)


def run_file_open_gui_entry(registry_dir: Path, path: Path) -> int:
    from appresolver.gui.file_open import run_file_open_gui

    return run_file_open_gui(registry_dir, path)


if __name__ == "__main__":
    raise SystemExit(main())
