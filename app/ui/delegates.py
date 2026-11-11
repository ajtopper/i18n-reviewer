from __future__ import annotations

from PySide6.QtCore import QAbstractItemModel, QModelIndex, QPersistentModelIndex, QRect, QSize, Qt
from PySide6.QtGui import QColor, QFont, QPainter
from PySide6.QtWidgets import QPlainTextEdit, QStyle, QStyledItemDelegate, QStyleOptionViewItem, QWidget

from app.core.project_manager import CellData, CellKind


_KIND_BADGES: dict[CellKind, tuple[str, str, str]] = {
    CellKind.MISSING: ("#f3f4f6", "MISSING", "#6b7280"),
    CellKind.EMPTY: ("#ffedd5", "[vazia]", "#c2410c"),
    CellKind.SAME_AS_BASE: ("#eff6ff", "= base", "#1d4ed8"),
    CellKind.ORPHAN: ("#fef3c7", "ÓRFÃ", "#b45309"),
    CellKind.NON_STRING: ("#e5e7eb", "[não-string]", "#4b5563"),
    CellKind.STRUCTURAL_CONFLICT: ("#fee2e2", "CONFLITO", "#b91c1c"),
    CellKind.NOT_APPLICABLE: ("#f9fafb", "", ""),
}


def _resolve_cell_style(cell: CellData) -> tuple[str, str, str]:
    if cell.marked_for_deletion:
        return ("#fee2e2", "REMOVER", "#b91c1c")
    if cell.is_missing:
        return _KIND_BADGES[CellKind.MISSING]
    if cell.kind in (CellKind.NON_STRING, CellKind.STRUCTURAL_CONFLICT, CellKind.NOT_APPLICABLE):
        return _KIND_BADGES[cell.kind]
    if cell.is_dirty:
        if cell.review_status == "reviewed":
            return ("#fef9c3", "EDITADO · OK", "#a16207")
        return ("#fef9c3", "EDITADO", "#b45309")
    if cell.review_status == "stale":
        return ("#ede9fe", "STALE", "#6d28d9")
    if cell.review_status == "reviewed":
        return ("#dcfce7", "OK", "#15803d")
    return _KIND_BADGES.get(cell.kind, ("", "", ""))


class StatusCellDelegate(QStyledItemDelegate):
    """Paints status backgrounds, top-right badges, capped row heights, and inline editors."""

    BADGE_STRIP_H = 18
    MAX_ROW_HEIGHT = 110

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._height_cache: dict[tuple[int, int, int, str], int] = {}

    def invalidate_cache(self) -> None:
        self._height_cache.clear()

    def sizeHint(
        self,
        option: QStyleOptionViewItem,
        index: QModelIndex | QPersistentModelIndex,
    ) -> QSize:
        width = max(80, option.rect.width())
        text = str(index.data(Qt.ItemDataRole.DisplayRole) or "")
        # Fast-path para strings curtas de linha única evita custo de layout Qt em 10k+ linhas
        if "\n" not in text and len(text) * 8 + 16 < width:
            return QSize(width, 44)
        key = (index.row(), index.column(), width, text)
        cached = self._height_cache.get(key)
        if cached is not None:
            return QSize(width, cached)

        base = super().sizeHint(option, index)
        extra = self.BADGE_STRIP_H + 4 if index.column() >= 2 else 4
        height = min(self.MAX_ROW_HEIGHT, max(44, base.height() + extra))
        if len(self._height_cache) > 40000:
            self._height_cache.clear()
        self._height_cache[key] = height
        return QSize(base.width(), height)

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionViewItem,
        index: QModelIndex | QPersistentModelIndex,
    ) -> None:
        cell = index.data(Qt.ItemDataRole.UserRole)
        if not isinstance(cell, CellData):
            super().paint(painter, option, index)
            return

        painter.save()
        bg_hex, badge_text, badge_hex = _resolve_cell_style(cell)

        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        if bg_hex and not selected:
            painter.fillRect(option.rect, QColor(bg_hex))

        text_opt = QStyleOptionViewItem(option)
        text_opt.rect = option.rect.adjusted(6, self.BADGE_STRIP_H, -4, -2)
        super().paint(painter, text_opt, index)

        if cell.kind == CellKind.STRUCTURAL_CONFLICT:
            stripe = QRect(option.rect.left(), option.rect.top(), 4, option.rect.height())
            painter.fillRect(stripe, QColor("#dc2626"))
        elif cell.kind in (CellKind.EMPTY, CellKind.ORPHAN, CellKind.NON_STRING):
            stripe = QRect(option.rect.left(), option.rect.top(), 4, option.rect.height())
            painter.fillRect(stripe, QColor("#f59e0b"))

        if badge_text:
            font = QFont("Segoe UI", 7, QFont.Weight.Bold)
            painter.setFont(font)
            width = max(36, len(badge_text) * 7 + 12)
            brect = QRect(option.rect.right() - width - 6, option.rect.top() + 3, width, 14)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(badge_hex))
            painter.drawRoundedRect(brect, 3, 3)
            painter.setPen(QColor("#ffffff"))
            painter.drawText(brect, Qt.AlignmentFlag.AlignCenter, badge_text)

        painter.restore()

    def createEditor(
        self,
        parent: QWidget,
        option: QStyleOptionViewItem,
        index: QModelIndex | QPersistentModelIndex,
    ) -> QWidget:
        editor = QPlainTextEdit(parent)
        editor.setTabChangesFocus(True)
        return editor

    def setEditorData(
        self,
        editor: QWidget,
        index: QModelIndex | QPersistentModelIndex,
    ) -> None:
        if isinstance(editor, QPlainTextEdit):
            editor.setPlainText(str(index.data(Qt.ItemDataRole.EditRole) or ""))

    def setModelData(
        self,
        editor: QWidget,
        model: QAbstractItemModel,
        index: QModelIndex | QPersistentModelIndex,
    ) -> None:
        if isinstance(editor, QPlainTextEdit):
            model.setData(index, editor.toPlainText(), Qt.ItemDataRole.EditRole)
