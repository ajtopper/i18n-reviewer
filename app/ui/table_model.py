from __future__ import annotations

from typing import Any

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QPersistentModelIndex, QSortFilterProxyModel, Qt
from PySide6.QtGui import QColor, QFont

from app.core.project_manager import CellData, CellKind, PackageSession, TableRowData


class TranslationTableModel(QAbstractTableModel):
    """Qt table model exposing unified base and target localization rows."""

    def __init__(self) -> None:
        super().__init__()
        self.session: PackageSession | None = None
        self.rows: list[TableRowData] = []
        self.base_lang: str = "en"
        self.target_langs: list[str] = []

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
                if self.session and lang in self.session.lang_conditionals:
                    cond = ", ".join(self.session.lang_conditionals[lang])
                    return f"{lang} [{cond}]"
                return lang
            return ""
        return str(section + 1)

    def get_row(self, row: int) -> TableRowData | None:
        if 0 <= row < len(self.rows):
            return self.rows[row]
        return None

    def get_cell(self, row: int, col: int) -> CellData | None:
        if col < 2 or row < 0 or row >= len(self.rows):
            return None
        lang = self.target_langs[col - 2]
        return self.rows[row].cells.get(lang)

    def data(
        self,
        index: QModelIndex | QPersistentModelIndex,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> Any:
        if not index.isValid():
            return None
        row_data = self.rows[index.row()]
        col = index.column()

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
            if cell.kind == CellKind.MISSING:
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
            if (col == 1 and row_data.base_text is None) or (
                cell is not None and cell.kind in (CellKind.MISSING, CellKind.NON_STRING, CellKind.EMPTY)
            ):
                font = QFont()
                font.setItalic(True)
                return font

        if role == Qt.ItemDataRole.ForegroundRole:
            if col == 1 and row_data.base_text is None:
                return QColor("#6b7280")
            cell = self.get_cell(index.row(), col)
            if cell is not None and cell.kind in (CellKind.MISSING, CellKind.NON_STRING, CellKind.NOT_APPLICABLE):
                return QColor("#6b7280")

        if role == Qt.ItemDataRole.UserRole:
            return self.get_cell(index.row(), col)

        return None


class PackageFilterProxyModel(QSortFilterProxyModel):
    """Filter proxy supporting per-source-file inspection in multi-file packages."""

    def __init__(self) -> None:
        super().__init__()
        self.file_filter: str | None = None

    def set_file_filter(self, rel_path: str | None) -> None:
        self.beginFilterChange()
        self.file_filter = rel_path or None
        self.endFilterChange(QSortFilterProxyModel.Direction.Rows)

    def filterAcceptsRow(
        self,
        source_row: int,
        source_parent: QModelIndex | QPersistentModelIndex,
    ) -> bool:
        if not self.file_filter:
            return True
        src_model = self.sourceModel()
        if not isinstance(src_model, TranslationTableModel):
            return True
        row_data = src_model.get_row(source_row)
        if row_data is None:
            return False
        if row_data.base_source_file == self.file_filter:
            return True
        return any(cell.source_file == self.file_filter for cell in row_data.cells.values())
