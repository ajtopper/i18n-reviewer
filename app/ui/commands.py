from __future__ import annotations

from typing import Callable

from PySide6.QtGui import QUndoCommand

from app.core.project_manager import CellData, CellSnapshot, TableRowData

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


class _BaseRowCommand(QUndoCommand):
    """Undoable row-wide base command capturing base cell, base text, and target review snapshots."""

    def __init__(
        self,
        title: str,
        row_data: TableRowData,
        row: int,
        col: int,
        notify_row: NotifyCallback,
    ) -> None:
        super().__init__(title)
        self.row_data = row_data
        self.row = row
        self.col = col
        self.notify_row = notify_row
        self._before_base_snap = row_data.base_cell.snapshot() if row_data.base_cell else None
        self._before_base_text = row_data.base_text
        self._before_targets = row_data.snapshot_target_cells()
        self._after_base_snap: CellSnapshot | None = None
        self._after_base_text: str | None = None
        self._after_targets: dict[str, CellSnapshot] | None = None

    def _apply_change(self) -> bool:
        raise NotImplementedError

    def undo(self) -> None:
        if self.row_data.base_cell is not None and self._before_base_snap is not None:
            self.row_data.base_cell.restore(self._before_base_snap)
        self.row_data.set_base_text(self._before_base_text)
        self.row_data.restore_target_cells(self._before_targets)
        self.notify_row(self.row, self.col)

    def redo(self) -> None:
        if self._after_base_snap is not None and self._after_targets is not None:
            if self.row_data.base_cell is not None:
                self.row_data.base_cell.restore(self._after_base_snap)
            self.row_data.set_base_text(self._after_base_text)
            self.row_data.restore_target_cells(self._after_targets)
            self.notify_row(self.row, self.col)
            return
        if self._apply_change():
            if self.row_data.base_cell is not None:
                self._after_base_snap = self.row_data.base_cell.snapshot()
            self._after_base_text = self.row_data.base_text
            self._after_targets = self.row_data.snapshot_target_cells()
            self.notify_row(self.row, self.col)


class EditBaseCellCommand(_BaseRowCommand):
    """Undoable command for editing a base-language cell and propagating stale state."""

    def __init__(
        self,
        row_data: TableRowData,
        new_value: str | None,
        row: int,
        col: int,
        notify_row: NotifyCallback,
    ) -> None:
        super().__init__(f"Edit Base ({row}, {col})", row_data, row, col, notify_row)
        self.new_value = new_value

    def _apply_change(self) -> bool:
        return self.row_data.apply_base_edit(self.new_value)


class RevertBaseCellCommand(_BaseRowCommand):
    """Undoable command for reverting a dirty base cell back to production."""

    def __init__(
        self,
        row_data: TableRowData,
        row: int,
        col: int,
        notify_row: NotifyCallback,
    ) -> None:
        super().__init__(f"Revert Base ({row}, {col})", row_data, row, col, notify_row)

    def _apply_change(self) -> bool:
        return self.row_data.revert_base_to_production()
