from __future__ import annotations

from PySide6.QtCore import QModelIndex, QPersistentModelIndex, QRect, QSize, Qt
from PySide6.QtGui import QColor, QFont, QPainter
from PySide6.QtWidgets import QStyle, QStyledItemDelegate, QStyleOptionViewItem

from app.core.project_manager import CellData, CellKind


_BADGE_STYLES: dict[CellKind, tuple[str, str, str]] = {
    CellKind.MISSING: ("#f3f4f6", "MISSING", "#6b7280"),
    CellKind.EMPTY: ("#ffedd5", "[vazia]", "#c2410c"),
    CellKind.SAME_AS_BASE: ("#eff6ff", "= base", "#1d4ed8"),
    CellKind.ORPHAN: ("#fef3c7", "ÓRFÃ", "#b45309"),
    CellKind.NON_STRING: ("#e5e7eb", "[não-string]", "#4b5563"),
    CellKind.STRUCTURAL_CONFLICT: ("#fee2e2", "CONFLITO", "#b91c1c"),
    CellKind.NOT_APPLICABLE: ("#f9fafb", "", ""),
}


class StatusCellDelegate(QStyledItemDelegate):
    """Paints status backgrounds, reserved top-right badges, and alert stripes."""

    BADGE_STRIP_H = 18

    def sizeHint(
        self,
        option: QStyleOptionViewItem,
        index: QModelIndex | QPersistentModelIndex,
    ) -> QSize:
        base = super().sizeHint(option, index)
        if index.column() >= 2:
            return QSize(base.width(), base.height() + self.BADGE_STRIP_H + 4)
        return base

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
        bg_hex, badge_text, badge_hex = _BADGE_STYLES.get(cell.kind, ("", "", ""))

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
            width = max(48, len(badge_text) * 7 + 12)
            brect = QRect(option.rect.right() - width - 6, option.rect.top() + 3, width, 14)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(badge_hex))
            painter.drawRoundedRect(brect, 3, 3)
            painter.setPen(QColor("#ffffff"))
            painter.drawText(brect, Qt.AlignmentFlag.AlignCenter, badge_text)

        painter.restore()

