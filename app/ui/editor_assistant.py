from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from PySide6.QtCore import QEvent, QObject, QTimer
from PySide6.QtGui import QAction, QColor, QContextMenuEvent, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import QMenu, QPlainTextEdit, QTextEdit

from app.core.glossary import GlossaryEntry, detect_base_glossary_matches
from app.core.spell_service import SpellService
from app.core.validator import CustomEnricherRule, IgnoredWarning, missing_tokens_for_translation
from app.ui.theme import LIGHT_TOKENS, ThemeTokens


@dataclass(frozen=True)
class EditorTextContext:
    """Metadata bundle used for real-time spellchecking and editor context-menu actions."""

    key_path: str
    lang: str
    base_text: str | None
    is_base_cell: bool
    glossary_entries: list[GlossaryEntry]
    custom_enrichers: list[CustomEnricherRule]
    ignored_warnings: list[IgnoredWarning]


class EditorAssistant(QObject):
    """Provides real-time spellcheck underlines and a unified rich context menu on QPlainTextEdit."""

    def __init__(
        self,
        editor: QPlainTextEdit,
        context_getter: Callable[[], EditorTextContext],
        spell_service: SpellService | None = None,
        tokens: ThemeTokens | None = None,
        on_personal_word_added: Callable[[str, str], None] | None = None,
        on_add_glossary_term: Callable[[str, str, str], object] | None = None,
        debounce_ms: int = 120,
    ) -> None:
        super().__init__(editor)
        self.editor = editor
        self._context_getter = context_getter
        self._spell_service = spell_service
        self._tokens = tokens or LIGHT_TOKENS
        self._on_personal_word_added = on_personal_word_added
        self._on_add_glossary_term = on_add_glossary_term
        self._misspelled_spans: list[tuple[int, int, str]] = []

        self._debounce_timer = QTimer(self)
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.setInterval(max(10, debounce_ms))
        self._debounce_timer.timeout.connect(self.refresh_spelling_now)

        self.editor.textChanged.connect(self._debounce_timer.start)
        self.editor.installEventFilter(self)

    def set_theme(self, tokens: ThemeTokens) -> None:
        """Update underline color for Light/Dark themes and repaint extra selections."""
        self._tokens = tokens
        self._apply_extra_selections()

    def misspelled_spans(self) -> list[tuple[int, int, str]]:
        """Return currently underlined (start, end, word) spans in the editor."""
        return list(self._misspelled_spans)

    def word_span_at(self, char_pos: int) -> tuple[int, int, str] | None:
        """Return the misspelled (start, end, word) span containing char_pos, if any."""
        for start, end, word in self._misspelled_spans:
            if start <= char_pos <= end:
                return start, end, word
        return None

    def refresh_spelling_now(self) -> list[tuple[int, int, str]]:
        """Synchronously recompute misspelled spans and apply wavy underlines."""
        self._debounce_timer.stop()
        if self._spell_service is None:
            self._misspelled_spans = []
            self._apply_extra_selections()
            return []
        ctx = self._context_getter()
        text = self.editor.toPlainText()
        if not text or not ctx.lang:
            self._misspelled_spans = []
            self._apply_extra_selections()
            return []
        self._misspelled_spans = self._spell_service.find_unknown_word_spans(
            ctx.lang,
            text,
            base_text=None if ctx.is_base_cell else ctx.base_text,
            glossary_entries=ctx.glossary_entries,
            custom_enrichers=ctx.custom_enrichers,
            ignored_warnings=ctx.ignored_warnings,
            key_path=ctx.key_path,
        )
        self._apply_extra_selections()
        return list(self._misspelled_spans)

    def _apply_extra_selections(self) -> None:
        if not self._misspelled_spans:
            self.editor.setExtraSelections([])
            return
        fmt = QTextCharFormat()
        fmt.setUnderlineStyle(QTextCharFormat.UnderlineStyle.SpellCheckUnderline)
        fmt.setUnderlineColor(QColor(self._tokens.error))
        doc = self.editor.document()
        selections: list[QTextEdit.ExtraSelection] = []
        for start, end, _word in self._misspelled_spans:
            cursor = QTextCursor(doc)
            cursor.setPosition(start)
            cursor.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
            sel = QTextEdit.ExtraSelection()
            sel.cursor = cursor
            sel.format = fmt
            selections.append(sel)
        self.editor.setExtraSelections(selections)

    def replace_span(self, start: int, end: int, replacement: str) -> None:
        """Replace a specific character span inside the editor while keeping focus active."""
        cursor = self.editor.textCursor()
        cursor.beginEditBlock()
        cursor.setPosition(start)
        cursor.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
        cursor.insertText(replacement)
        cursor.endEditBlock()
        self.editor.setTextCursor(cursor)
        self.refresh_spelling_now()

    def insert_at_cursor(self, text: str, cursor_pos: int | None = None) -> None:
        """Insert token or glossary text at the target or current cursor position."""
        cursor = self.editor.textCursor()
        if cursor_pos is not None and not cursor.hasSelection():
            cursor.setPosition(max(0, min(cursor_pos, len(self.editor.toPlainText()))))
        cursor.insertText(text)
        self.editor.setTextCursor(cursor)
        self.refresh_spelling_now()

    def _add_personal_word(self, lang: str, word: str) -> None:
        if self._spell_service is None:
            return
        if self._spell_service.add_personal(lang, word):
            self.refresh_spelling_now()
            if self._on_personal_word_added is not None:
                self._on_personal_word_added(lang, word)

    def build_context_menu(self, cursor_pos: int | None = None) -> QMenu:
        """Build unified editor context menu prepending spell, token, and glossary actions."""
        menu = self.editor.createStandardContextMenu()
        first_std = menu.actions()[0] if menu.actions() else None
        ctx = self._context_getter()
        effective_pos = self.editor.textCursor().position() if cursor_pos is None else cursor_pos
        self.refresh_spelling_now()

        custom_actions: list[QAction] = []

        def _add_sep() -> None:
            if custom_actions and not custom_actions[-1].isSeparator():
                sep = QAction(menu)
                sep.setSeparator(True)
                custom_actions.append(sep)

        # 1. Spell suggestions + Add to dictionary for the word under cursor
        span = self.word_span_at(effective_pos)
        if span is not None and self._spell_service is not None:
            start, end, bad_word = span
            for sugg in self._spell_service.suggest(ctx.lang, bad_word, limit=5):
                act_fix = QAction(f"Fix '{bad_word}' → '{sugg}'", menu)
                act_fix.triggered.connect(
                    lambda _=False, s=start, e=end, rep=sugg: self.replace_span(s, e, rep)
                )
                custom_actions.append(act_fix)
            act_pwl = QAction(f"Add '{bad_word}' to dictionary", menu)
            act_pwl.triggered.connect(
                lambda _=False, lg=ctx.lang, bw=bad_word: self._add_personal_word(lg, bw)
            )
            custom_actions.append(act_pwl)

        # 2. Missing protected tokens (for translation cells)
        if not ctx.is_base_cell:
            missing_toks = missing_tokens_for_translation(
                ctx.base_text,
                self.editor.toPlainText(),
                custom_enrichers=ctx.custom_enrichers,
            )
            if missing_toks:
                _add_sep()
                for tok in missing_toks[:8]:
                    act_tok = QAction(f"Insert missing token: {tok}", menu)
                    act_tok.triggered.connect(
                        lambda _=False, t=tok, cp=effective_pos: self.insert_at_cursor(t, cp)
                    )
                    custom_actions.append(act_tok)

            # 3. Glossary actions
            matches = detect_base_glossary_matches(
                ctx.base_text,
                ctx.glossary_entries,
                custom_enrichers=ctx.custom_enrichers,
            )
            applied_any = False
            for entry in matches[:6]:
                pref = entry.preferred_translation(ctx.lang)
                if pref is None:
                    continue
                if not applied_any:
                    _add_sep()
                    applied_any = True
                act_gloss = QAction(f"Apply glossary: {entry.term} → {pref}", menu)
                act_gloss.triggered.connect(
                    lambda _=False, val=pref, cp=effective_pos: self.insert_at_cursor(val, cp)
                )
                custom_actions.append(act_gloss)

            if self._on_add_glossary_term is not None:
                if not applied_any:
                    _add_sep()
                selected_txt = (
                    self.editor.textCursor().selectedText().replace("\u2029", " ").strip()
                )
                prefill_term = selected_txt or (ctx.base_text or "").strip()[:60]
                prefill_trans = "" if selected_txt else self.editor.toPlainText().strip()[:80]
                cb = self._on_add_glossary_term
                act_add_gloss = QAction("Add term to glossary...", menu)
                act_add_gloss.triggered.connect(
                    lambda _=False, pt=prefill_term, tr=prefill_trans, lg=ctx.lang: cb(pt, tr, lg)
                )
                custom_actions.append(act_add_gloss)

        if custom_actions:
            _add_sep()
            if first_std is not None:
                menu.insertActions(first_std, custom_actions)
            else:
                menu.addActions(custom_actions)
        return menu

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if watched is self.editor and event.type() == QEvent.Type.ContextMenu:
            if isinstance(event, QContextMenuEvent):
                if event.reason() == QContextMenuEvent.Reason.Mouse:
                    char_pos = self.editor.cursorForPosition(event.pos()).position()
                else:
                    char_pos = self.editor.textCursor().position()
                menu = self.build_context_menu(cursor_pos=char_pos)
                menu.exec(event.globalPos())
                menu.deleteLater()
                return True
        return super().eventFilter(watched, event)


def attach_editor_assistant(
    editor: QPlainTextEdit,
    *,
    context_getter: Callable[[], EditorTextContext],
    spell_service: SpellService | None = None,
    tokens: ThemeTokens | None = None,
    on_personal_word_added: Callable[[str, str], None] | None = None,
    on_add_glossary_term: Callable[[str, str, str], object] | None = None,
) -> EditorAssistant:
    """Attach an EditorAssistant to a QPlainTextEdit and store a reference on it."""
    assistant = EditorAssistant(
        editor=editor,
        context_getter=context_getter,
        spell_service=spell_service,
        tokens=tokens,
        on_personal_word_added=on_personal_word_added,
        on_add_glossary_term=on_add_glossary_term,
    )
    editor.setProperty("_editor_assistant", assistant)
    return assistant
