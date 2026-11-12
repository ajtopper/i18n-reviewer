from __future__ import annotations

from typing import Any, Literal

from PySide6.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    QPersistentModelIndex,
    QSortFilterProxyModel,
    Qt,
    Signal,
)
from PySide6.QtGui import QColor, QFont, QUndoStack

from app.core.project_manager import CellData, CellKind, PackageSession, TableRowData
from app.ui.commands import EditCellCommand

StatusFilterMode = Literal["all", "pending", "edited", "alerts", "glossary"]
BASE_ISSUES_ROLE = int(Qt.ItemDataRole.UserRole) + 1


class TranslationTableModel(QAbstractTableModel):
    """Qt table model exposing unified base and target localization rows."""

    cell_edited = Signal(int, int)

    def __init__(self, undo_stack: QUndoStack | None = None) -> None:
        super().__init__()
        self.session: PackageSession | None = None
        self.rows: list[TableRowData] = []
        self.base_lang: str = "en"
        self.target_langs: list[str] = []
        self.missing_spell_langs: set[str] = set()
        self.missing_spell_tooltips: dict[str, str] = {}
        self.undo_stack = undo_stack

    def set_session(self, session: PackageSession) -> None:
        self.beginResetModel()
        self.session = session
        self.rows = list(session.rows)
        self.base_lang = session.base_lang
        self.target_langs = list(session.target_langs)
        self.endResetModel()

    def rowCount(
        self,
        parent: QModelIndex | QPersistentModelIndex = QModelIndex(),
    ) -> int:
        if parent.isValid():
            return 0
        return len(self.rows)

    def columnCount(
        self,
        parent: QModelIndex | QPersistentModelIndex = QModelIndex(),
    ) -> int:
        if parent.isValid():
            return 0
        return 2 + len(self.target_langs)

    def headerData(
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> Any:
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.ToolTipRole:
            idx = section - 2
            if 0 <= idx < len(self.target_langs):
                return self.missing_spell_tooltips.get(self.target_langs[idx])
            return None
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if orientation == Qt.Orientation.Horizontal:
            if section == 0:
                return "KEY_PATH"
            if section == 1:
                return f"{self.base_lang} (Base)"
            idx = section - 2
            if 0 <= idx < len(self.target_langs):
                lang = self.target_langs[idx]
                label = lang
                if self.session and lang in self.session.lang_conditionals:
                    cond = ", ".join(self.session.lang_conditionals[lang])
                    label = f"{lang} [{cond}]"
                if lang in self.missing_spell_langs:
                    label = f"{label} (sem ortografia)"
                return label
            return ""
        return str(section + 1)

    def flags(self, index: QModelIndex | QPersistentModelIndex) -> Qt.ItemFlag:
        base = super().flags(index)
        if not index.isValid() or index.column() < 2:
            return base
        cell = self.get_cell(index.row(), index.column())
        if cell is None or not cell.can_edit():
            return base
        return base | Qt.ItemFlag.ItemIsEditable

    def get_row(self, row: int) -> TableRowData | None:
        if 0 <= row < len(self.rows):
            return self.rows[row]
        return None

    def get_cell(self, row: int, col: int) -> CellData | None:
        if col < 2 or row < 0 or row >= len(self.rows):
            return None
        lang = self.target_langs[col - 2]
        return self.rows[row].cells.get(lang)

    def notify_cell_changed(self, row: int, col: int) -> None:
        if 0 <= row < len(self.rows):
            self.rows[row].rebuild_search_blob()
        idx = self.index(row, col)
        self.dataChanged.emit(idx, idx)
        self.cell_edited.emit(row, col)

    def data(
        self,
        index: QModelIndex | QPersistentModelIndex,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> Any:
        if not index.isValid():
            return None
        row_data = self.rows[index.row()]
        col = index.column()

        if role == Qt.ItemDataRole.EditRole:
            if col < 2:
                return None
            cell = self.get_cell(index.row(), col)
            return cell.local_value or "" if cell is not None else ""

        if role == Qt.ItemDataRole.DisplayRole:
            if col == 0:
                return row_data.key_path
            if col == 1:
                return row_data.base_text if row_data.base_text is not None else "(ausente na base)"
            cell = self.get_cell(index.row(), col)
            if cell is None:
                return ""
            if cell.kind == CellKind.NOT_APPLICABLE:
                return "—"
            if cell.is_missing:
                return "(ausente)"
            if cell.kind == CellKind.NON_STRING:
                return f"[não-string: {cell.raw_type}]"
            if cell.kind == CellKind.EMPTY:
                return '""'
            return cell.local_value or ""

        if role == Qt.ItemDataRole.FontRole:
            if col == 0:
                return QFont("Consolas", 9)
            cell = self.get_cell(index.row(), col)
            if cell is not None and cell.marked_for_deletion:
                font = QFont()
                font.setStrikeOut(True)
                return font
            if (col == 1 and row_data.base_text is None) or (
                cell is not None and (cell.is_missing or cell.kind in (CellKind.NON_STRING, CellKind.EMPTY))
            ):
                font = QFont()
                font.setItalic(True)
                return font

        if role == Qt.ItemDataRole.ForegroundRole:
            if col == 1 and row_data.base_text is None:
                return QColor("#6b7280")
            cell = self.get_cell(index.row(), col)
            if cell is not None and (
                cell.is_missing or cell.kind in (CellKind.NON_STRING, CellKind.NOT_APPLICABLE)
            ):
                return QColor("#6b7280")

        if role == Qt.ItemDataRole.UserRole:
            return self.get_cell(index.row(), col)

        if role == BASE_ISSUES_ROLE and col == 1:
            return row_data.base_issues

        return None

    def setData(
        self,
        index: QModelIndex | QPersistentModelIndex,
        value: Any,
        role: int = Qt.ItemDataRole.EditRole,
    ) -> bool:
        if role != Qt.ItemDataRole.EditRole or not index.isValid() or index.column() < 2:
            return False
        row_data = self.get_row(index.row())
        cell = self.get_cell(index.row(), index.column())
        if row_data is None or cell is None:
            return False
        new_text = str(value)
        if not cell.will_apply_edit(new_text):
            return False

        if self.undo_stack is not None:
            cmd = EditCellCommand(
                cell=cell,
                base_text=row_data.base_text,
                new_value=new_text,
                row=index.row(),
                col=index.column(),
                notify=self.notify_cell_changed,
            )
            self.undo_stack.push(cmd)
            return True

        if cell.apply_edit(new_text, base_text=row_data.base_text):
            self.notify_cell_changed(index.row(), index.column())
            return True
        return False


class PackageFilterProxyModel(QSortFilterProxyModel):
    """Filter proxy supporting source-file, review-status, and pre-normalized search."""

    def __init__(self) -> None:
        super().__init__()
        self.file_filter: str | None = None
        self.status_filter: StatusFilterMode = "all"
        self.search_query: str = ""

    def set_file_filter(self, rel_path: str | None) -> None:
        self.beginFilterChange()
        self.file_filter = rel_path or None
        self.endFilterChange(QSortFilterProxyModel.Direction.Rows)

    def set_status_filter(self, mode: StatusFilterMode) -> None:
        self.beginFilterChange()
        self.status_filter = mode
        self.endFilterChange(QSortFilterProxyModel.Direction.Rows)

    def set_search_query(self, query: str) -> None:
        normalized = query.strip().lower()
        if normalized == self.search_query:
            return
        self.beginFilterChange()
        self.search_query = normalized
        self.endFilterChange(QSortFilterProxyModel.Direction.Rows)

    def filterAcceptsRow(
        self,
        source_row: int,
        source_parent: QModelIndex | QPersistentModelIndex,
    ) -> bool:
        src_model = self.sourceModel()
        if not isinstance(src_model, TranslationTableModel):
            return True
        row_data = src_model.get_row(source_row)
        if row_data is None:
            return False

        if self.file_filter:
            in_base = row_data.base_source_file == self.file_filter
            in_target = any(c.source_file == self.file_filter for c in row_data.cells.values())
            if not (in_base or in_target):
                return False

        if self.status_filter == "pending":
            if not any(c.is_pending for c in row_data.cells.values()):
                return False
        elif self.status_filter == "edited":
            if not any(c.is_dirty for c in row_data.cells.values()):
                return False
        elif self.status_filter == "alerts":
            if not any(
                c.validation_severity in ("critical", "warning")
                for c in row_data.cells.values()
            ):
                return False
        elif self.status_filter == "glossary":
            if not any(bool(c.active_glossary_issues) for c in row_data.cells.values()):
                return False

        if self.search_query and not row_data.matches_search(self.search_query):
            return False

        return True
