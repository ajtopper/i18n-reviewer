from __future__ import annotations

import re
from typing import TYPE_CHECKING

from PySide6.QtCore import QEvent, QModelIndex, QObject, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)

from app.core.project_manager import CellData, TableRowData
from app.core.replace_service import (
    compile_find_pattern,
    find_matches_in_text,
    replace_all_in_text,
    replace_first_in_text,
)
from app.ui.commands import EditBaseCellCommand, EditCellCommand
from app.ui.theme import handle_zoom_key_event

if TYPE_CHECKING:
    from app.ui.main_window import MainWindow


class FindReplaceDialog(QDialog):
    """Modeless Find & Replace dialog scoped to visible rows with token protection and batch undo."""

    def __init__(self, main_window: MainWindow) -> None:
        super().__init__(main_window)
        self._win = main_window
        self._current_match_offset: int = 0
        self._last_match_cell_key: tuple[int, int] | None = None

        self.setWindowTitle("Find & Replace")
        z = self._win.theme_manager.zoom
        self.resize(round(480 * min(z, 1.5)), round(260 * min(z, 1.5)))

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.find_input = QLineEdit()
        self.find_input.setPlaceholderText("Text to find...")
        self.find_input.textChanged.connect(self._on_criteria_changed)
        self.find_input.returnPressed.connect(self.find_next)
        form.addRow("Find:", self.find_input)

        self.replace_input = QLineEdit()
        self.replace_input.setPlaceholderText("Replacement text...")
        form.addRow("Replace with:", self.replace_input)

        self.column_combo = QComboBox()
        self.column_combo.currentIndexChanged.connect(self._on_criteria_changed)
        form.addRow("Target column:", self.column_combo)
        layout.addLayout(form)

        opts_row = QHBoxLayout()
        self.case_cb = QCheckBox("Case-sensitive")
        self.case_cb.toggled.connect(self._on_criteria_changed)
        self.whole_word_cb = QCheckBox("Whole word")
        self.whole_word_cb.toggled.connect(self._on_criteria_changed)
        self.protect_tokens_cb = QCheckBox("Protect technical tokens")
        self.protect_tokens_cb.setChecked(True)
        self.protect_tokens_cb.toggled.connect(self._on_criteria_changed)
        opts_row.addWidget(self.case_cb)
        opts_row.addWidget(self.whole_word_cb)
        opts_row.addWidget(self.protect_tokens_cb)
        opts_row.addStretch()
        layout.addLayout(opts_row)

        self.preview_label = QLabel("Enter text to search visible rows.")
        layout.addWidget(self.preview_label)

        btn_row = QHBoxLayout()
        self.btn_find_next = QPushButton("Find Next")
        self.btn_find_next.clicked.connect(self.find_next)
        self.btn_replace = QPushButton("Replace")
        self.btn_replace.clicked.connect(self.replace_current)
        self.btn_replace_all = QPushButton("Replace All")
        self.btn_replace_all.setObjectName("PrimaryCTA")
        self.btn_replace_all.clicked.connect(self.replace_all)
        self.btn_close = QPushButton("Close")
        self.btn_close.clicked.connect(self.close)
        btn_row.addWidget(self.btn_find_next)
        btn_row.addWidget(self.btn_replace)
        btn_row.addWidget(self.btn_replace_all)
        btn_row.addStretch()
        btn_row.addWidget(self.btn_close)
        layout.addLayout(btn_row)

        self.installEventFilter(self)
        self.refresh_columns()
        self.refresh_preview()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if (
            event.type() == QEvent.Type.KeyPress
            and isinstance(event, QKeyEvent)
            and handle_zoom_key_event(event, self._win.theme_manager)
        ):
            return True
        return super().eventFilter(watched, event)

    def refresh_columns(self, preferred_col: int | None = None) -> None:
        """Populate target column selector from currently loaded and visible language columns."""
        prev_data = preferred_col if preferred_col is not None else self.column_combo.currentData()
        self.column_combo.blockSignals(True)
        self.column_combo.clear()
        self.column_combo.addItem("All visible columns", None)
        session = self._win.session
        if session is not None:
            model = self._win.table_model
            for col in range(1, model.columnCount()):
                if self._win.table.isColumnHidden(col):
                    continue
                header = str(model.headerData(col, Qt.Orientation.Horizontal) or f"Col {col}")
                self.column_combo.addItem(header, col)
        if prev_data is not None:
            idx = self.column_combo.findData(prev_data)
            if idx >= 0:
                self.column_combo.setCurrentIndex(idx)
            elif self.column_combo.count() > 1:
                self.column_combo.setCurrentIndex(0)
        self.column_combo.blockSignals(False)
        self.refresh_preview()

    def _on_criteria_changed(self) -> None:
        self._current_match_offset = 0
        self._last_match_cell_key = None
        self.refresh_preview()

    def _target_columns(self) -> list[int]:
        chosen = self.column_combo.currentData()
        if isinstance(chosen, int):
            return [chosen] if not self._win.table.isColumnHidden(chosen) else []
        return [
            col
            for col in range(1, self._win.table_model.columnCount())
            if not self._win.table.isColumnHidden(col)
        ]

    def _compiled_pattern(self) -> re.Pattern[str] | None:
        return compile_find_pattern(
            self.find_input.text(),
            case_sensitive=self.case_cb.isChecked(),
            whole_word=self.whole_word_cb.isChecked(),
        )

    def _iter_visible_cells(self) -> list[tuple[QModelIndex, int, int, TableRowData, CellData]]:
        """Enumerate visible proxy cells in target columns in row-major order."""
        cols = self._target_columns()
        proxy = self._win.proxy_model
        model = self._win.table_model
        items: list[tuple[QModelIndex, int, int, TableRowData, CellData]] = []
        for prow in range(proxy.rowCount()):
            for col in cols:
                pidx = proxy.index(prow, col)
                sidx = proxy.mapToSource(pidx)
                if not sidx.isValid():
                    continue
                row_data = model.get_row(sidx.row())
                cell = model.get_cell(sidx.row(), col)
                if row_data is None or cell is None:
                    continue
                items.append((pidx, sidx.row(), col, row_data, cell))
        return items

    def preview_counts(self) -> tuple[int, int, int]:
        """Return (eligible_occurrences, eligible_cells, skipped_protected_occurrences)."""
        pat = self._compiled_pattern()
        if pat is None or self._win.session is None:
            return 0, 0, 0
        protect = self.protect_tokens_cb.isChecked()
        enrichers = self._win.session.custom_enrichers
        occ_total = 0
        cell_total = 0
        skipped_total = 0
        for _pidx, _srow, _col, _row_data, cell in self._iter_visible_cells():
            if not cell.can_edit() or not cell.local_value:
                continue
            spans, skipped = find_matches_in_text(
                cell.local_value,
                pat,
                protect_tokens=protect,
                custom_enrichers=enrichers,
            )
            skipped_total += skipped
            if spans:
                occ_total += len(spans)
                cell_total += 1
        return occ_total, cell_total, skipped_total

    def refresh_preview(self) -> None:
        """Update the preview counter and button enabled states."""
        query = self.find_input.text()
        if not query:
            self.preview_label.setText("Enter text to search visible rows.")
            self.btn_find_next.setEnabled(False)
            self.btn_replace.setEnabled(False)
            self.btn_replace_all.setEnabled(False)
            return
        occ, cells, skipped = self.preview_counts()
        self.btn_find_next.setEnabled(occ > 0)
        self.btn_replace.setEnabled(occ > 0)
        self.btn_replace_all.setEnabled(occ > 0)
        if occ == 0 and skipped == 0:
            self.preview_label.setText("No matches in visible editable cells.")
            return
        msg = f"{occ} match(es) in {cells} editable cell(s)"
        if skipped > 0:
            msg += f" ({skipped} protected skipped)"
        self.preview_label.setText(msg)

    def _ordered_candidates_from_current(
        self,
    ) -> list[tuple[QModelIndex, int, int, TableRowData, CellData]]:
        items = self._iter_visible_cells()
        if not items:
            return []
        cur = self._win.table.currentIndex()
        if not cur.isValid():
            return items
        cur_tuple = (cur.row(), cur.column())
        start_idx = 0
        for i, (pidx, *_rest) in enumerate(items):
            if (pidx.row(), pidx.column()) >= cur_tuple:
                start_idx = i
                break
        return items[start_idx:] + items[:start_idx]

    def find_next(self) -> bool:
        """Select and scroll to the next visible editable cell with an eligible match."""
        pat = self._compiled_pattern()
        if pat is None or self._win.session is None:
            return False
        candidates = self._ordered_candidates_from_current()
        if not candidates:
            self.refresh_preview()
            return False

        cur = self._win.table.currentIndex()
        cur_src = self._win.proxy_model.mapToSource(cur) if cur.isValid() else QModelIndex()
        cur_key = (cur_src.row(), cur_src.column()) if cur_src.isValid() else None
        # Skip current cell first if we are already positioned on it, wrapping back if it is the only match
        if len(candidates) > 1 and cur_key is not None and (candidates[0][1], candidates[0][2]) == cur_key:
            candidates = candidates[1:] + candidates[:1]

        protect = self.protect_tokens_cb.isChecked()
        enrichers = self._win.session.custom_enrichers
        for pidx, srow, col, _row_data, cell in candidates:
            if not cell.can_edit() or not cell.local_value:
                continue
            spans, _ = find_matches_in_text(
                cell.local_value,
                pat,
                protect_tokens=protect,
                custom_enrichers=enrichers,
            )
            if spans:
                self._win.table.setCurrentIndex(pidx)
                self._win.table.scrollTo(pidx)
                self._last_match_cell_key = (srow, col)
                self._current_match_offset = 0
                return True
        self.refresh_preview()
        return False

    def _apply_cell_edit(
        self,
        srow: int,
        col: int,
        row_data: TableRowData,
        cell: CellData,
        new_value: str,
    ) -> bool:
        if not cell.will_apply_edit(new_value):
            return False
        if col == 1:
            self._win.undo_stack.push(
                EditBaseCellCommand(
                    row_data=row_data,
                    new_value=new_value,
                    row=srow,
                    col=col,
                    notify_row=self._win.table_model.notify_row_changed,
                )
            )
            return True
        self._win.undo_stack.push(
            EditCellCommand(
                cell=cell,
                base_text=row_data.base_text,
                new_value=new_value,
                row=srow,
                col=col,
                notify=self._win.table_model.notify_cell_changed,
            )
        )
        return True

    def replace_current(self) -> bool:
        """Replace the current eligible match in the selected cell and advance to the next."""
        pat = self._compiled_pattern()
        if pat is None or self._win.session is None:
            return False
        self._win.commit_active_inline_editor()

        pos = self._win._current_source_pos()
        protect = self.protect_tokens_cb.isChecked()
        enrichers = self._win.session.custom_enrichers
        replacement = self.replace_input.text()

        if pos is not None and pos[1] in self._target_columns():
            srow, col = pos
            row_data = self._win.table_model.get_row(srow)
            cell = self._win.table_model.get_cell(srow, col)
            if row_data is not None and cell is not None and cell.can_edit() and cell.local_value:
                start_at = self._current_match_offset if self._last_match_cell_key == (srow, col) else 0
                new_val, span, _ = replace_first_in_text(
                    cell.local_value,
                    pat,
                    replacement,
                    start_pos=start_at,
                    protect_tokens=protect,
                    custom_enrichers=enrichers,
                )
                if span is None and start_at > 0:
                    new_val, span, _ = replace_first_in_text(
                        cell.local_value,
                        pat,
                        replacement,
                        start_pos=0,
                        protect_tokens=protect,
                        custom_enrichers=enrichers,
                    )
                if span is not None and self._apply_cell_edit(srow, col, row_data, cell, new_val):
                    rem_spans, _ = find_matches_in_text(
                        new_val,
                        pat,
                        protect_tokens=protect,
                        custom_enrichers=enrichers,
                    )
                    next_in_same = [s for s in rem_spans if s[0] >= span[1]]
                    if next_in_same:
                        self._last_match_cell_key = (srow, col)
                        self._current_match_offset = next_in_same[0][0]
                    else:
                        self.find_next()
                    self.refresh_preview()
                    return True

        return self.find_next()

    def replace_all(self) -> int:
        """Replace all eligible matches in visible rows within one QUndoStack macro."""
        pat = self._compiled_pattern()
        if pat is None or self._win.session is None:
            return 0
        self._win.commit_active_inline_editor()

        protect = self.protect_tokens_cb.isChecked()
        enrichers = self._win.session.custom_enrichers
        replacement = self.replace_input.text()
        query = self.find_input.text()

        pending_edits: list[tuple[int, int, TableRowData, CellData, str]] = []
        skipped_total = 0
        for _pidx, srow, col, row_data, cell in self._iter_visible_cells():
            if not cell.can_edit() or not cell.local_value:
                continue
            res = replace_all_in_text(
                cell.local_value,
                pat,
                replacement,
                protect_tokens=protect,
                custom_enrichers=enrichers,
            )
            skipped_total += res.skipped_protected_count
            if res.eligible_count > 0 and cell.will_apply_edit(res.new_text):
                pending_edits.append((srow, col, row_data, cell, res.new_text))

        if not pending_edits:
            self.refresh_preview()
            return 0

        self._win.begin_batch_edit()
        try:
            self._win.undo_stack.beginMacro(f"Replace All '{query}' -> '{replacement}'")
            try:
                for srow, col, row_data, cell, new_val in pending_edits:
                    self._apply_cell_edit(srow, col, row_data, cell, new_val)
            finally:
                self._win.undo_stack.endMacro()
        finally:
            self._win.end_batch_edit({srow for srow, *_ in pending_edits})

        self._last_match_cell_key = None
        self._current_match_offset = 0
        self.refresh_preview()
        msg = f"Replaced {len(pending_edits)} cell(s)."
        if skipped_total > 0:
            msg += f" ({skipped_total} protected occurrence(s) skipped.)"
        self._win.statusBar().showMessage(msg)
        return len(pending_edits)
