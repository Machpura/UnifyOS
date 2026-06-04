from __future__ import annotations

from pathlib import Path

import pytest

from appresolver.gui import __main__ as gui_main


def test_gui_main_without_open_dispatches_manager(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[Path] = []

    def fake_run_manager_gui(registry_dir: Path) -> int:
        calls.append(registry_dir)
        return 17

    monkeypatch.setattr(gui_main, "run_manager_gui", fake_run_manager_gui)

    exit_code = gui_main.main(["--registry-dir", "/tmp/appresolver-state/apps"])

    assert exit_code == 17
    assert calls == [Path("/tmp/appresolver-state/apps")]


def test_gui_main_with_open_dispatches_file_open(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    calls: list[tuple[Path, Path]] = []
    source_path = tmp_path / "Example.AppImage"

    def fake_run_file_open_gui_entry(registry_dir: Path, path: Path) -> int:
        calls.append((registry_dir, path))
        return 23

    monkeypatch.setattr(gui_main, "run_file_open_gui_entry", fake_run_file_open_gui_entry)

    exit_code = gui_main.main(
        ["--registry-dir", "/tmp/appresolver-state/apps", "--open", str(source_path)]
    )

    assert exit_code == 23
    assert calls == [(Path("/tmp/appresolver-state/apps"), source_path)]
