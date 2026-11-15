from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QTextCharFormat
from PySide6.QtWidgets import QMessageBox, QPlainTextEdit
from pytestqt.qtbot import QtBot

from app.core.glossary import GlossaryEntry
from app.core.spell_service import SpellService
from app.ui.editor_assistant import EditorAssistant
from app.ui.main_window import ExpandedEditorDialog, MainWindow


def _write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def test_spell_service_find_unknown_word_spans_masks_tech_base_and_glossary(tmp_path: Path) -> None:
    svc = SpellService(app_data_dir=tmp_path / "appdata")
    if not svc.is_available("pt-BR"):
        return

    text = "Caza {caza} com @UUID[Compendium.caza.items]{Espada} e DNTWord."
    spans = svc.find_unknown_word_spans(
        "pt-BR",
        text,
        base_text="House DNTWord",
        glossary_entries=[
            GlossaryEntry(term="Sword", do_not_translate=False, translations={"pt-BR": ["Espada"]})
        ],
    )
    words = [w for _, _, w in spans]
    assert "Caza" in words
    assert "caza" not in words  # inside {caza}
    assert "DNTWord" not in words  # present in base
    start, end, word = spans[0]
    assert text[start:end] == word


def test_realtime_underline_and_unified_context_menu_in_inline_and_expanded_editors(
    qtbot: QtBot,
    tmp_path: Path,
    monkeypatch: object,
) -> None:
    monkeypatch.setattr(  # type: ignore[attr-defined]
        QMessageBox,
        "question",
        lambda *a, **kw: QMessageBox.StandardButton.Discard,
    )

    pkg = tmp_path / "spell-ui-mod"
    _write_json(
        pkg / "module.json",
        {
            "id": "spell-ui-mod",
            "languages": [
                {"lang": "en", "path": "lang/en.json"},
                {"lang": "pt-BR", "path": "lang/pt-BR.json"},
                {"lang": "eo", "path": "lang/eo.json"},
            ],
        },
    )
    _write_json(pkg / "lang/en.json", {"K1": "The sword of {hero} shines."})
    _write_json(pkg / "lang/pt-BR.json", {"K1": "A spada brilha."})
    _write_json(pkg / "lang/eo.json", {"K1": "La glavo de {hero} brilas."})

    app_data = tmp_path / "appdata"
    win = MainWindow(app_data_dir=app_data)
    qtbot.addWidget(win)
    win.open_package_manifest(pkg / "module.json")
    assert win.session is not None
    win.session.project_glossary = [
        GlossaryEntry(term="sword", translations={"pt-BR": ["espada"]})
    ]
    win.show()
    qtbot.waitExposed(win)

    # 1) Open inline editor in pt-BR cell (row 0, col 2)
    idx_pt = win.proxy_model.index(0, 2)
    win.table.setCurrentIndex(idx_pt)
    win.table.edit(idx_pt)
    inline_ed = win.table.focusWidget()
    assert isinstance(inline_ed, QPlainTextEdit)
    assistant = inline_ed.property("_editor_assistant")
    assert isinstance(assistant, EditorAssistant)

    # Initial misspelled word 'spada' is underlined immediately
    spans = assistant.misspelled_spans()
    assert any(w == "spada" for _, _, w in spans)
    extra = inline_ed.extraSelections()
    assert any(
        sel.format.underlineStyle() == QTextCharFormat.UnderlineStyle.SpellCheckUnderline
        for sel in extra
    )

    # Context menu at 'spada' position includes spell fix, Add to dictionary, missing token, glossary, and standard actions
    spada_pos = inline_ed.toPlainText().index("spada") + 1
    menu = assistant.build_context_menu(cursor_pos=spada_pos)
    texts = [act.text() for act in menu.actions() if not act.isSeparator()]
    assert any(t.startswith("Fix 'spada' → ") for t in texts)
    assert "Add 'spada' to dictionary" in texts
    assert "Insert missing token: {hero}" in texts
    assert "Apply glossary: sword → espada" in texts
    assert "Add term to glossary..." in texts
    assert any("Copy" in t for t in texts)
    assert any("Select All" in t for t in texts)

    # Trigger Fix 'spada' -> suggestion updates editor text and clears underline
    fix_act = next(a for a in menu.actions() if a.text().startswith("Fix 'spada' → "))
    fix_act.trigger()
    assert "spada" not in inline_ed.toPlainText()

    # Insert missing token via context menu action
    menu2 = assistant.build_context_menu(cursor_pos=len(inline_ed.toPlainText()))
    tok_act = next(a for a in menu2.actions() if a.text() == "Insert missing token: {hero}")
    tok_act.trigger()
    assert "{hero}" in inline_ed.toPlainText()

    # Commit inline edit
    win.commit_active_inline_editor()

    # 2) Test real-time debounced underline & Add to dictionary inside ExpandedEditorDialog
    dlg = ExpandedEditorDialog(
        "The sword of {hero} shines.",
        "Uma palavrasupererrada brilha.",
        "K1",
        "pt-BR",
        win,
        glossary_entries=win.merged_glossary(),
        tokens=win.theme_manager.tokens,
        theme_manager=win.theme_manager,
        spell_service=win.spell_service,
        on_personal_word_added=win._on_editor_personal_word_added,
    )
    qtbot.addWidget(dlg)
    dlg_assistant = dlg.target_edit.property("_editor_assistant")
    assert isinstance(dlg_assistant, EditorAssistant)
    assert any(w == "palavrasupererrada" for _, _, w in dlg_assistant.misspelled_spans())

    # Typing a new unknown word updates underlines via debounce
    dlg.target_edit.setPlainText("Texto com errouwu desconhecido.")
    qtbot.waitUntil(
        lambda: any(w == "errouwu" for _, _, w in dlg_assistant.misspelled_spans()),
        timeout=1000,
    )

    # Add 'errouwu' to dictionary clears underline immediately
    err_pos = dlg.target_edit.toPlainText().index("errouwu") + 1
    dlg_menu = dlg_assistant.build_context_menu(cursor_pos=err_pos)
    pwl_act = next(a for a in dlg_menu.actions() if a.text() == "Add 'errouwu' to dictionary")
    pwl_act.trigger()
    assert not any(w == "errouwu" for _, _, w in dlg_assistant.misspelled_spans())
    dlg.close()

    # 3) Language without Hunspell dictionary ('eo', col 3) produces no false underlines
    idx_eo = win.proxy_model.index(0, 3)
    win.table.setCurrentIndex(idx_eo)
    win.table.edit(idx_eo)
    eo_ed = win.table.focusWidget()
    assert isinstance(eo_ed, QPlainTextEdit)
    eo_assistant = eo_ed.property("_editor_assistant")
    assert isinstance(eo_assistant, EditorAssistant)
    assert eo_assistant.misspelled_spans() == []
    win.commit_active_inline_editor()
    win.close()
