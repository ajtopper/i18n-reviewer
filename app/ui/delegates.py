from __future__ import annotations

from typing import Callable

from PySide6.QtCore import QAbstractItemModel, QModelIndex, QPersistentModelIndex, QRect, QSize, Qt
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter
from PySide6.QtWidgets import QPlainTextEdit, QStyle, QStyledItemDelegate, QStyleOptionViewItem, QWidget

from app.core.project_manager import CellData, CellKind
from app.core.spell_service import SpellService
from app.core.validator import CustomEnricherRule
from app.ui.editor_assistant import EditorAssistant, EditorTextContext, attach_editor_assistant
from app.ui.glossary_dialog import GlossaryCellContext, attach_ctrl_space_glossary_popup
from app.ui.highlighter import TokenHighlighter
from app.ui.table_model import BASE_ISSUES_ROLE
from app.ui.theme import DEFAULT_ZOOM_FACTOR, LIGHT_TOKENS, ThemeTokens, clamp_zoom_factor


_KIND_TO_BADGE_KEY: dict[CellKind, str] = {
    CellKind.MISSING: "MISSING",
    CellKind.EMPTY: "EMPTY",
    CellKind.SAME_AS_BASE: "SAME_AS_BASE",
    CellKind.ORPHAN: "ORPHAN",
    CellKind.NON_STRING: "NON_STRING",
    CellKind.STRUCTURAL_CONFLICT: "CONFLICT",
    CellKind.NOT_APPLICABLE: "NOT_APPLICABLE",
}


def _resolve_cell_style(cell: CellData, tokens: ThemeTokens = LIGHT_TOKENS) -> tuple[str, str, str]:
    badges = tokens.badge_colors
    if cell.is_base_cell:
        if cell.kind in (CellKind.NON_STRING, CellKind.STRUCTURAL_CONFLICT, CellKind.NOT_APPLICABLE):
            return badges[_KIND_TO_BADGE_KEY[cell.kind]]
        if cell.is_dirty:
            return badges["EDITED"]
        if cell.kind == CellKind.EMPTY:
            return badges["EMPTY"]
        if cell.is_missing:
            return badges["MISSING"]
        return ("", "", "")
    if cell.marked_for_deletion:
        return badges["REMOVE"]
    if cell.is_missing:
        return badges["MISSING"]
    if cell.kind in (CellKind.NON_STRING, CellKind.STRUCTURAL_CONFLICT, CellKind.NOT_APPLICABLE):
        return badges[_KIND_TO_BADGE_KEY[cell.kind]]
    if cell.is_dirty:
        if cell.review_status == "reviewed":
            return badges["EDITED_OK"]
        return badges["EDITED"]
    if cell.review_status == "stale":
        return badges["STALE"]
    if cell.review_status == "reviewed":
        return badges["OK"]
    key = _KIND_TO_BADGE_KEY.get(cell.kind)
    return badges[key] if key else ("", "", "")


class StatusCellDelegate(QStyledItemDelegate):
    """Paints status backgrounds, top-right badges, capped row heights, and inline editors."""

    BADGE_STRIP_H = 18
    MAX_ROW_HEIGHT = 110

    def __init__(
        self,
        parent: QWidget | None = None,
        custom_enrichers_getter: Callable[[], list[CustomEnricherRule]] | None = None,
        live_text_changed: Callable[[CellData, str], None] | None = None,
        glossary_context_getter: Callable[[QModelIndex | QPersistentModelIndex], GlossaryCellContext]
        | None = None,
        tokens: ThemeTokens | None = None,
        spell_service: SpellService | None = None,
        editor_context_getter: Callable[[QModelIndex | QPersistentModelIndex], EditorTextContext]
        | None = None,
        on_personal_word_added: Callable[[str, str], None] | None = None,
        on_add_glossary_term: Callable[[str, str, str], object] | None = None,
    ) -> None:
        super().__init__(parent)
        self._height_cache: dict[tuple[int, int, int, float, bool, str], int] = {}
        self._custom_enrichers_getter = custom_enrichers_getter
        self._live_text_changed = live_text_changed
        self._glossary_context_getter = glossary_context_getter
        self._tokens = tokens or LIGHT_TOKENS
        self._spell_service = spell_service
        self._editor_context_getter = editor_context_getter
        self._on_personal_word_added = on_personal_word_added
        self._on_add_glossary_term = on_add_glossary_term
        self._zoom: float = DEFAULT_ZOOM_FACTOR
        self._compact: bool = False
        self._cursor_positions: dict[int, int] = {}
        self._populating_editor = False

    def set_theme(self, tokens: ThemeTokens) -> None:
        """Update delegate colors from ThemeTokens."""
        self._tokens = tokens

    def set_zoom(self, zoom: float) -> None:
        """Scale badge, padding, and row height metrics proportionally to the UI zoom factor."""
        clamped = clamp_zoom_factor(zoom)
        if clamped != self._zoom:
            self._zoom = clamped
            self._height_cache.clear()

    def set_compact(self, compact: bool) -> None:
        """Toggle compact minimum row height and clear cached row heights."""
        if compact != self._compact:
            self._compact = compact
            self._height_cache.clear()

    def badge_strip_height(self) -> int:
        """Return scaled vertical space reserved for the status badge strip."""
        badge_pt = max(6, round(7 * self._zoom))
        fm = QFontMetrics(QFont("Segoe UI", badge_pt, QFont.Weight.Bold))
        badge_h = max(round(14 * self._zoom), fm.height() + max(2, round(2 * self._zoom)))
        return max(round(self.BADGE_STRIP_H * self._zoom), badge_h + max(3, round(4 * self._zoom)))

    def min_row_height(self) -> int:
        """Return scaled minimum row height for normal or compact density."""
        base_min = 34 if self._compact else 44
        return max(28, round(base_min * self._zoom))

    def max_row_height(self) -> int:
        """Return scaled maximum row height cap."""
        return max(80, round(self.MAX_ROW_HEIGHT * self._zoom))

    def cursor_pos_for(self, cell: CellData) -> int | None:
        """Return last known editor cursor offset for a cell, if any."""
        return self._cursor_positions.get(id(cell))

    def set_cursor_pos_for(self, cell: CellData, pos: int) -> None:
        self._cursor_positions[id(cell)] = max(0, pos)

    def invalidate_cache(self) -> None:
        self._height_cache.clear()
        self._cursor_positions.clear()

    def sizeHint(
        self,
        option: QStyleOptionViewItem,
        index: QModelIndex | QPersistentModelIndex,
    ) -> QSize:
        width = max(80, option.rect.width())
        text = str(index.data(Qt.ItemDataRole.DisplayRole) or "")
        min_h = self.min_row_height()
        char_px = max(6.0, 8.0 * self._zoom)
        pad_px = round(16 * self._zoom)
        # Fast-path para strings curtas de linha única evita custo de layout Qt em 10k+ linhas
        if "\n" not in text and len(text) * char_px + pad_px < width:
            return QSize(width, min_h)
        key = (index.row(), index.column(), width, self._zoom, self._compact, text)
        cached = self._height_cache.get(key)
        if cached is not None:
            return QSize(width, cached)

        base = super().sizeHint(option, index)
        extra_pad = max(3, round(4 * self._zoom))
        extra = self.badge_strip_height() + extra_pad if index.column() >= 1 else extra_pad
        height = min(self.max_row_height(), max(min_h, base.height() + extra))
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
        stripe_w = max(3, round(4 * self._zoom))
        if not isinstance(cell, CellData):
            super().paint(painter, option, index)
            if index.column() == 1:
                base_issues = index.data(BASE_ISSUES_ROLE)
                if isinstance(base_issues, list) and base_issues:
                    painter.save()
                    stripe = QRect(option.rect.left(), option.rect.top(), stripe_w, option.rect.height())
                    painter.fillRect(stripe, QColor(self._tokens.stripe_info))
                    painter.restore()
            return

        painter.save()
        bg_hex, badge_text, badge_hex = _resolve_cell_style(cell, self._tokens)

        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        if bg_hex and not selected:
            painter.fillRect(option.rect, QColor(bg_hex))

        strip_h = self.badge_strip_height()
        text_opt = QStyleOptionViewItem(option)
        text_opt.rect = option.rect.adjusted(
            max(4, round(6 * self._zoom)),
            strip_h,
            -max(3, round(4 * self._zoom)),
            -max(2, round(2 * self._zoom)),
        )
        super().paint(painter, text_opt, index)

        val_sev = cell.validation_severity
        if cell.kind == CellKind.STRUCTURAL_CONFLICT or val_sev == "critical":
            stripe = QRect(option.rect.left(), option.rect.top(), stripe_w, option.rect.height())
            painter.fillRect(stripe, QColor(self._tokens.stripe_critical))
        elif val_sev == "warning" or cell.kind in (CellKind.EMPTY, CellKind.ORPHAN, CellKind.NON_STRING):
            stripe = QRect(option.rect.left(), option.rect.top(), stripe_w, option.rect.height())
            painter.fillRect(stripe, QColor(self._tokens.stripe_warning))
        elif index.column() == 1 and index.data(BASE_ISSUES_ROLE):
            stripe = QRect(option.rect.left(), option.rect.top(), stripe_w, option.rect.height())
            painter.fillRect(stripe, QColor(self._tokens.stripe_info))

        if badge_text:
            badge_pt = max(6, round(7 * self._zoom))
            font = QFont("Segoe UI", badge_pt, QFont.Weight.Bold)
            painter.setFont(font)
            fm = QFontMetrics(font)
            width = max(round(36 * self._zoom), fm.horizontalAdvance(badge_text) + round(12 * self._zoom))
            badge_h = max(round(14 * self._zoom), fm.height() + max(2, round(2 * self._zoom)))
            top_pad = max(2, round(3 * self._zoom))
            right_pad = max(4, round(6 * self._zoom))
            radius = max(2, round(3 * self._zoom))
            brect = QRect(option.rect.right() - width - right_pad, option.rect.top() + top_pad, width, badge_h)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(badge_hex))
            painter.drawRoundedRect(brect, radius, radius)
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
        editor.setFont(option.font)
        editor.setTabChangesFocus(True)
        rules = self._custom_enrichers_getter() if self._custom_enrichers_getter else []
        TokenHighlighter(editor.document(), custom_enrichers=rules, tokens=self._tokens)
        cell = index.data(Qt.ItemDataRole.UserRole)
        if isinstance(cell, CellData):
            def _on_cursor_changed(c: CellData = cell, ed: QPlainTextEdit = editor) -> None:
                if not self._populating_editor:
                    self.set_cursor_pos_for(c, ed.textCursor().position())

            editor.cursorPositionChanged.connect(_on_cursor_changed)
            if self._live_text_changed is not None:
                cb = self._live_text_changed

                def _on_live_text(c: CellData = cell, ed: QPlainTextEdit = editor) -> None:
                    if not self._populating_editor:
                        cb(c, ed.toPlainText())

                editor.textChanged.connect(_on_live_text)
        if self._glossary_context_getter is not None:
            ctx = self._glossary_context_getter(index)

            def _get_ctx() -> GlossaryCellContext:
                return ctx

            attach_ctrl_space_glossary_popup(
                editor,
                context_getter=_get_ctx,
                custom_enrichers_getter=self._custom_enrichers_getter,
            )
        if self._editor_context_getter is not None:
            pidx = QPersistentModelIndex(index)
            ctx_getter = self._editor_context_getter

            def _get_editor_ctx() -> EditorTextContext:
                return ctx_getter(pidx)

            attach_editor_assistant(
                editor,
                context_getter=_get_editor_ctx,
                spell_service=self._spell_service,
                tokens=self._tokens,
                on_personal_word_added=self._on_personal_word_added,
                on_add_glossary_term=self._on_add_glossary_term,
            )
        return editor

    def setEditorData(
        self,
        editor: QWidget,
        index: QModelIndex | QPersistentModelIndex,
    ) -> None:
        if isinstance(editor, QPlainTextEdit):
            self._populating_editor = True
            try:
                editor.setPlainText(str(index.data(Qt.ItemDataRole.EditRole) or ""))
            finally:
                self._populating_editor = False
            assistant = editor.property("_editor_assistant")
            if isinstance(assistant, EditorAssistant):
                assistant.refresh_spelling_now()

    def setModelData(
        self,
        editor: QWidget,
        model: QAbstractItemModel,
        index: QModelIndex | QPersistentModelIndex,
    ) -> None:
        if isinstance(editor, QPlainTextEdit):
            cell = index.data(Qt.ItemDataRole.UserRole)
            if isinstance(cell, CellData):
                self.set_cursor_pos_for(cell, editor.textCursor().position())
            model.setData(index, editor.toPlainText(), Qt.ItemDataRole.EditRole)
