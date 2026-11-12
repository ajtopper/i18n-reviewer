from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from PySide6.QtCore import QEvent, QObject, QPoint, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.core.glossary import (
    GlossaryEntry,
    detect_base_glossary_matches,
    export_glossary_csv,
    export_glossary_json,
    import_glossary_csv,
    import_glossary_json,
    merge_glossaries,
)
from app.core.validator import CustomEnricherRule


@dataclass(frozen=True)
class GlossaryCellContext:
    """Bundled cell context for glossary autocompletion in delegates."""

    base_text: str
    lang: str
    entries: list[GlossaryEntry]


def open_glossary_popup_at(
    parent_widget: QWidget,
    global_pos: QPoint,
    *,
    base_text: str,
    lang: str,
    entries: list[GlossaryEntry],
    custom_enrichers: list[CustomEnricherRule] | None,
    on_selected: Callable[[str], None],
) -> QListWidget | None:
    """Build and show the Ctrl+Space glossary completion popup, returning it for focus/testing."""
    matches = detect_base_glossary_matches(base_text, entries, custom_enrichers=custom_enrichers)
    if not matches:
        return None

    popup = QListWidget(parent_widget)
    popup.setWindowFlags(Qt.WindowType.Popup)
    popup.setMinimumWidth(260)
    for entry in matches:
        options = entry.accepted_translations(lang)
        if not options:
            continue
        for idx, opt in enumerate(options):
            suffix = " (preferred)" if idx == 0 and len(options) > 1 else ""
            item = QListWidgetItem(f"{entry.term} → {opt}{suffix}")
            item.setData(Qt.ItemDataRole.UserRole, opt)
            popup.addItem(item)

    if popup.count() == 0:
        popup.deleteLater()
        return None

    popup.setCurrentRow(0)
    committed = False

    def _commit_item(item: QListWidgetItem) -> None:
        nonlocal committed
        if committed:
            return
        committed = True
        text = str(item.data(Qt.ItemDataRole.UserRole) or "")
        if text:
            on_selected(text)
        popup.close()

    popup.itemActivated.connect(_commit_item)
    popup.itemClicked.connect(_commit_item)
    popup.move(global_pos)
    popup.show()
    popup.setFocus()
    return popup


class _GlossaryCompletionFilter(QObject):
    """Event filter handling Ctrl+Space inside a QPlainTextEdit to pick glossary terms."""

    def __init__(
        self,
        editor: QPlainTextEdit,
        context_getter: Callable[[], GlossaryCellContext],
        custom_enrichers_getter: Callable[[], list[CustomEnricherRule]] | None = None,
    ) -> None:
        super().__init__(editor)
        self.editor = editor
        self._context_getter = context_getter
        self._custom_enrichers_getter = custom_enrichers_getter
        self._popup: QListWidget | None = None

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if watched is self.editor and event.type() == QEvent.Type.KeyPress:
            if isinstance(event, QKeyEvent):
                is_ctrl_space = (
                    event.key() == Qt.Key.Key_Space
                    and bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier)
                )
                if is_ctrl_space:
                    self._open_popup()
                    return True
        return super().eventFilter(watched, event)

    def _insert_selected(self, text: str) -> None:
        cursor = self.editor.textCursor()
        cursor.insertText(text)
        self.editor.setTextCursor(cursor)

    def _open_popup(self) -> None:
        if self._popup is not None:
            self._popup.close()
            self._popup.deleteLater()
            self._popup = None

        ctx = self._context_getter()
        custom = self._custom_enrichers_getter() if self._custom_enrichers_getter else None
        rect = self.editor.cursorRect()
        self._popup = open_glossary_popup_at(
            self.editor,
            self.editor.mapToGlobal(rect.bottomLeft()),
            base_text=ctx.base_text,
            lang=ctx.lang,
            entries=ctx.entries,
            custom_enrichers=custom,
            on_selected=self._insert_selected,
        )


def attach_ctrl_space_glossary_popup(
    editor: QPlainTextEdit,
    context_getter: Callable[[], GlossaryCellContext],
    custom_enrichers_getter: Callable[[], list[CustomEnricherRule]] | None = None,
) -> None:
    """Attach Ctrl+Space glossary autocomplete popup to any QPlainTextEdit."""
    flt = _GlossaryCompletionFilter(
        editor=editor,
        context_getter=context_getter,
        custom_enrichers_getter=custom_enrichers_getter,
    )
    editor.installEventFilter(flt)


class GlossaryDialog(QDialog):
    """Two-level glossary manager supporting Global/Project scopes, variants, and JSON/CSV I/O."""

    def __init__(
        self,
        global_entries: list[GlossaryEntry],
        project_entries: list[GlossaryEntry],
        target_langs: list[str],
        *,
        prefill_term: str = "",
        prefill_translation: str = "",
        prefill_lang: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Glossary Manager (Global + Project)")
        self.resize(780, 500)
        self._global_entries = list(global_entries)
        self._project_entries = list(project_entries)
        self._target_langs = list(dict.fromkeys(target_langs or (["pt-BR"] if not prefill_lang else [prefill_lang])))
        if prefill_lang and prefill_lang not in self._target_langs:
            self._target_langs.append(prefill_lang)

        layout = QVBoxLayout(self)

        top_bar = QHBoxLayout()
        top_bar.addWidget(QLabel("Active scope:"))
        self.scope_combo = QComboBox()
        self.scope_combo.addItem("Project (.i18nproj)", "project")
        self.scope_combo.addItem("Global (glossary.json)", "global")
        self.scope_combo.currentIndexChanged.connect(self._reload_list)
        top_bar.addWidget(self.scope_combo)
        top_bar.addStretch()

        self.btn_import_json = QPushButton("Import JSON...")
        self.btn_import_json.clicked.connect(
            lambda: self._import_with("JSON (*.json)", "Import JSON Glossary", import_glossary_json)
        )
        self.btn_export_json = QPushButton("Export JSON...")
        self.btn_export_json.clicked.connect(
            lambda: self._export_with("glossary.json", "JSON (*.json)", "Export JSON Glossary", export_glossary_json)
        )
        self.btn_import_csv = QPushButton("Import CSV...")
        self.btn_import_csv.clicked.connect(
            lambda: self._import_with("CSV (*.csv)", "Import CSV Glossary", import_glossary_csv)
        )
        self.btn_export_csv = QPushButton("Export CSV...")
        self.btn_export_csv.clicked.connect(
            lambda: self._export_with("glossary.csv", "CSV (*.csv)", "Export CSV Glossary", export_glossary_csv)
        )
        for btn in (self.btn_import_json, self.btn_export_json, self.btn_import_csv, self.btn_export_csv):
            top_bar.addWidget(btn)
        layout.addLayout(top_bar)

        cols = QHBoxLayout()
        left_col = QVBoxLayout()
        self.entry_list = QListWidget()
        self.entry_list.currentRowChanged.connect(self._on_entry_selected)
        left_col.addWidget(self.entry_list, 1)
        self.btn_remove = QPushButton("Remove selected")
        self.btn_remove.clicked.connect(self._remove_selected)
        left_col.addWidget(self.btn_remove)
        cols.addLayout(left_col, 2)

        form_box = QFormLayout()
        self.term_input = QLineEdit(prefill_term)
        self.variants_input = QLineEdit()
        self.variants_input.setPlaceholderText("E.g., Spell Slots | Spells")
        self.case_cb = QCheckBox("Case sensitive (case_sensitive)")
        self.dnt_cb = QCheckBox("Do not translate (do_not_translate)")
        self.notes_input = QLineEdit()
        form_box.addRow("Source term:", self.term_input)
        form_box.addRow("Source variants (|):", self.variants_input)
        form_box.addRow("", self.case_cb)
        form_box.addRow("", self.dnt_cb)
        form_box.addRow("Notes:", self.notes_input)

        self.lang_inputs: dict[str, QLineEdit] = {}
        for lang in self._target_langs:
            ed = QLineEdit(prefill_translation if lang == prefill_lang else "")
            ed.setPlaceholderText("Preferred | accepted 2 | accepted 3")
            self.lang_inputs[lang] = ed
            form_box.addRow(f"Translations ({lang}):", ed)

        self.btn_save_entry = QPushButton("Save term to scope")
        self.btn_save_entry.clicked.connect(self.save_form_entry)
        form_box.addRow(self.btn_save_entry)
        cols.addLayout(form_box, 3)
        layout.addLayout(cols, 1)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self._reload_list()

    def _current_bucket(self) -> list[GlossaryEntry]:
        return self._global_entries if self.scope_combo.currentData() == "global" else self._project_entries

    def _set_current_bucket(self, updated: list[GlossaryEntry]) -> None:
        if self.scope_combo.currentData() == "global":
            self._global_entries = updated
        else:
            self._project_entries = updated

    def _reload_list(self) -> None:
        self.entry_list.clear()
        for entry in self._current_bucket():
            badge = "DNT" if entry.do_not_translate else f"{len(entry.translations)} language(s)"
            self.entry_list.addItem(QListWidgetItem(f"{entry.term} [{badge}]"))

    def _on_entry_selected(self, row: int) -> None:
        bucket = self._current_bucket()
        if not (0 <= row < len(bucket)):
            return
        entry = bucket[row]
        self.term_input.setText(entry.term)
        self.variants_input.setText(" | ".join(entry.source_variants))
        self.case_cb.setChecked(entry.case_sensitive)
        self.dnt_cb.setChecked(entry.do_not_translate)
        self.notes_input.setText(entry.notes)
        for lang, ed in self.lang_inputs.items():
            ed.setText(" | ".join(entry.translations.get(lang, [])))

    def _matches_entry_key(self, existing: GlossaryEntry, term: str, case_sensitive: bool) -> bool:
        if existing.case_sensitive or case_sensitive:
            return existing.term == term
        return existing.term.casefold() == term.casefold()

    def save_form_entry(self) -> bool:
        """Create or update an entry in the currently selected scope while preserving unshown languages."""
        term = self.term_input.text().strip()
        if not term:
            return False
        variants = [v.strip() for v in self.variants_input.text().split("|") if v.strip()]
        case_sensitive = self.case_cb.isChecked()
        bucket = list(self._current_bucket())
        match_idx = next(
            (i for i, e in enumerate(bucket) if self._matches_entry_key(e, term, case_sensitive)),
            -1,
        )
        translations: dict[str, list[str]] = (
            {k: list(v) for k, v in bucket[match_idx].translations.items()} if match_idx >= 0 else {}
        )
        for lang, ed in self.lang_inputs.items():
            vals = [v.strip() for v in ed.text().split("|") if v.strip()]
            if vals:
                translations[lang] = vals
            else:
                translations.pop(lang, None)
        entry = GlossaryEntry(
            term=term,
            source_variants=variants,
            case_sensitive=case_sensitive,
            do_not_translate=self.dnt_cb.isChecked(),
            notes=self.notes_input.text().strip(),
            translations=translations,
        )
        if match_idx >= 0:
            bucket[match_idx] = entry
        else:
            bucket.append(entry)
        self._set_current_bucket(bucket)
        self._reload_list()
        return True

    def _remove_selected(self) -> None:
        row = self.entry_list.currentRow()
        bucket = list(self._current_bucket())
        if 0 <= row < len(bucket):
            bucket.pop(row)
            self._set_current_bucket(bucket)
            self._reload_list()

    def _import_with(
        self,
        file_filter: str,
        title: str,
        importer: Callable[[Path], list[GlossaryEntry]],
    ) -> None:
        path_str, _ = QFileDialog.getOpenFileName(self, title, "", file_filter)
        if not path_str:
            return
        try:
            imported = importer(Path(path_str))
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, title, str(exc))
            return
        merged = merge_glossaries(self._current_bucket(), imported)
        self._set_current_bucket(merged)
        self._reload_list()

    def _export_with(
        self,
        default_name: str,
        file_filter: str,
        title: str,
        exporter: Callable[[list[GlossaryEntry], Path], None],
    ) -> None:
        path_str, _ = QFileDialog.getSaveFileName(self, title, default_name, file_filter)
        if path_str:
            exporter(self._current_bucket(), Path(path_str))

    def global_entries(self) -> list[GlossaryEntry]:
        return list(self._global_entries)

    def project_entries(self) -> list[GlossaryEntry]:
        return list(self._project_entries)
