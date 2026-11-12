from __future__ import annotations

from typing import Callable

from PySide6.QtGui import QUndoCommand

from app.core.project_manager import CellData, CellSnapshot

NotifyCallback = Callable[[int, int], None]


class _BaseCellCommand(QUndoCommand):
    """Shared undo/redo command base storing cell reference and snapshot."""

    def __init__(
        self,
        title: str,
        cell: CellData,
        row: int,
        col: int,
        notify: NotifyCallback,
    ) -> None:
        super().__init__(title)
        self.cell = cell
        self.row = row
        self.col = col
        self.notify = notify
        self._before: CellSnapshot = cell.snapshot()

    def undo(self) -> None:
        self.cell.restore(self._before)
        self.notify(self.row, self.col)


class EditCellCommand(_BaseCellCommand):
    """Undoable command for editing a translation cell's text."""

    def __init__(
        self,
        cell: CellData,
        base_text: str | None,
        new_value: str | None,
        row: int,
        col: int,
        notify: NotifyCallback,
    ) -> None:
        super().__init__(f"Edit ({row}, {col})", cell, row, col, notify)
        self.base_text = base_text
        self.new_value = new_value

    def redo(self) -> None:
        if self.cell.apply_edit(self.new_value, base_text=self.base_text):
            self.notify(self.row, self.col)


class ReviewCellCommand(_BaseCellCommand):
    """Undoable command for explicitly marking a cell as reviewed."""

    def __init__(
        self,
        cell: CellData,
        row: int,
        col: int,
        notify: NotifyCallback,
    ) -> None:
        super().__init__(f"Review ({row}, {col})", cell, row, col, notify)

    def redo(self) -> None:
        if self.cell.mark_reviewed():
            self.notify(self.row, self.col)


class RevertCellCommand(_BaseCellCommand):
    """Undoable command for reverting local edits/deletion back to production."""

    def __init__(
        self,
        cell: CellData,
        base_text: str | None,
        row: int,
        col: int,
        notify: NotifyCallback,
    ) -> None:
        super().__init__(f"Revert ({row}, {col})", cell, row, col, notify)
        self.base_text = base_text

    def redo(self) -> None:
        if self.cell.revert_to_production(base_text=self.base_text):
            self.notify(self.row, self.col)


class ToggleOrphanDeletionCommand(_BaseCellCommand):
    """Undoable command for marking or unmarking an orphan key for removal."""

    def __init__(
        self,
        cell: CellData,
        flag: bool,
        row: int,
        col: int,
        notify: NotifyCallback,
    ) -> None:
        super().__init__(f"Remove orphan ({row}, {col})", cell, row, col, notify)
        self.flag = flag

    def redo(self) -> None:
        if self.cell.set_marked_for_deletion(self.flag):
            self.notify(self.row, self.col)
