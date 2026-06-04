from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QObject, Signal, Slot


class Worker(QObject):
    result = Signal(object)
    error = Signal(object)
    finished = Signal()

    def __init__(self, task: Callable[[], Any]) -> None:
        super().__init__()
        self.task = task

    @Slot()
    def run(self) -> None:
        try:
            self.result.emit(self.task())
        except Exception as exc:  # noqa: BLE001 - surfaced to the GUI log.
            self.error.emit(exc)
        finally:
            self.finished.emit()
