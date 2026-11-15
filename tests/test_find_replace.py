from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMessageBox
from pytestqt.qtbot import QtBot

from app.core.replace_service import (
    compile_find_pattern,
    find_matches_in_text,
    replace_all_in_text,
    replace_first_in_text,
)
from app.core.validator import CustomEnricherRule
from app.ui.main_window import MainWindow


def _write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def test_replace_service_protects_technical_tokens_while_replacing_prose_and_labels() -> None:
    text = (
        "The hero {hero} uses {{hero}} and @UUID[Compendium.hero.items]{hero blade} "
        "plus <span class=\"hero\">hero</span> at https://hero.example/hero."
    )
    pat = compile_find_pattern("hero", case_sensitive=False, whole_word=True)
    assert pat is not None

    spans, skipped = find_matches_in_text(text, pat, protect_tokens=True)
    # Eligible: leading "hero", enricher label "hero" in {hero blade}, HTML inner "hero"
    assert len(spans) == 3
    # Protected skipped: {hero}, {{hero}}, Compendium.hero.items, class="hero", https://hero.example/hero (2x)
    assert skipped >= 5

    res = replace_all_in_text(text, pat, "champion", protect_tokens=True)
    assert res.eligible_count == 3
    assert res.skipped_protected_count == skipped
    assert "{hero}" in res.new_text
    assert "{{hero}}" in res.new_text
    assert "@UUID[Compendium.hero.items]{champion blade}" in res.new_text
    assert '<span class="hero">champion</span>' in res.new_text
    assert "https://hero.example/hero" in res.new_text
    assert res.new_text.startswith("The champion ")

    # Custom enricher protection
    custom = [CustomEnricherRule(name="Macro", pattern=r"(?P<tech>%[A-Z_]+%)")]
    res_custom = replace_all_in_text(
        "Use %HERO_NAME% for HERO",
        compile_find_pattern("HERO", case_sensitive=True, whole_word=False),  # type: ignore[arg-type]
        "CHAMPION",
        protect_tokens=True,
        custom_enrichers=custom,
    )
    assert res_custom.new_text == "Use %HERO_NAME% for CHAMPION"
    assert res_custom.skipped_protected_count == 1

    # Single replace starting after offset
    single, span, _ = replace_first_in_text("hero one and hero two", pat, "mage", start_pos=5)
    assert span is not None
    assert single == "hero one and mage two"


def test_ctrl_h_find_replace_interactive_and_batch_undo_macro(
    qtbot: QtBot,
    tmp_path: Path,
    monkeypatch: object,
) -> None:
    monkeypatch.setattr(  # type: ignore[attr-defined]
        QMessageBox,
        "question",
        lambda *a, **kw: QMessageBox.StandardButton.Discard,
    )
    pkg = tmp_path / "replace-mod"
    _write_json(
        pkg / "module.json",
        {
            "id": "replace-mod",
            "languages": [
                {"lang": "en", "path": "lang/en.json"},
                {"lang": "pt-BR", "path": "lang/pt-BR.json"},
                {"lang": "es", "path": "lang/es.json"},
            ],
        },
    )
    _write_json(
        pkg / "lang/en.json",
        {
            "K1": "Old sword",
            "K2": "Old shield",
            "K3": "Old {old} armor",
            "K4": "Hidden filter row",
        },
    )
    _write_json(
        pkg / "lang/pt-BR.json",
        {
            "K1": "Velha espada",
            "K2": "Velha armadura",
            "K3": "Velha {velha} bota",
            "K4": "Velha capa",
        },
    )
    _write_json(
        pkg / "lang/es.json",
        {
            "K1": "Espada vieja",
            "K2": "Escudo viejo",
            "K3": "Armadura vieja",
            "K4": "Capa vieja",
        },
    )

    win = MainWindow(app_data_dir=tmp_path / "appdata")
    qtbot.addWidget(win)
    win.open_package_manifest(pkg / "module.json")
    win.show()
    qtbot.waitExposed(win)

    # Mark K2 pt-BR (and es) as reviewed beforehand to verify Replace All downgrades it to unreviewed
    c2 = win.table_model.get_cell(1, 2)
    c2_es = win.table_model.get_cell(1, 3)
    assert c2 is not None and c2_es is not None
    c2.mark_reviewed()
    c2_es.mark_reviewed()
    assert c2.review_status == "reviewed"

    # Filter table to only "K" matching "Velha" -> wait, filter out K4 by searching "espada|armadura|bota"
    # Let's filter using search_input = "armadura" or simpler: "K1" / "Pending" - let's use search "a" vs "Velha"
    # Actually let's filter status to Pending Only so K2 (reviewed) is hidden, OR keep All and test file/search filter!
    win.search_input.setText("Velha")
    qtbot.waitUntil(lambda: win.proxy_model.rowCount() == 4, timeout=1000)
    # Narrow out K4 by putting "Velha " -> still 4; let's test K1..K3 by searching "Velha " after editing K4 or using a word only in K1-K3:
    win.search_input.setText("")
    qtbot.waitUntil(lambda: win.proxy_model.rowCount() == 4, timeout=1000)
    # Put focus on pt-BR column (col 2)
    win.table.setCurrentIndex(win.proxy_model.index(0, 2))

    # Open Ctrl+H dialog
    qtbot.keyClick(win.table, Qt.Key.Key_H, Qt.KeyboardModifier.ControlModifier)
    dlg = win._replace_dialog
    assert dlg is not None and dlg.isVisible()
    assert dlg.column_combo.currentData() == 2  # pt-BR pre-selected

    dlg.find_input.setText("Velha")
    dlg.replace_input.setText("Antiga")
    occ, cells, skipped = dlg.preview_counts()
    assert occ == 4
    assert cells == 4
    assert skipped == 1  # {velha} in K3 is protected
    assert "4 match(es) in 4 editable cell(s)" in dlg.preview_label.text()
    assert "1 protected skipped" in dlg.preview_label.text()

    # Interactive Find Next + single Replace on K1
    dlg.find_next()
    cur_src = win.proxy_model.mapToSource(win.table.currentIndex())
    assert cur_src.row() == 1  # moved from K1 (row 0) to K2 (row 1)

    # Replace K2 singly
    assert dlg.replace_current() is True
    assert c2.local_value == "Antiga armadura"
    assert c2.review_status == "unreviewed"
    win.undo_stack.undo()
    assert c2.local_value == "Velha armadura"
    assert c2.review_status == "reviewed"

    # Filter out K4 via search query ("espada" only matches K1 -> wait, test Replace All on filtered rows!)
    win.search_input.setText("Velha")
    qtbot.waitUntil(lambda: win.proxy_model.rowCount() == 4, timeout=1000)
    # Filter to Pending Only -> K2 (which is reviewed) is excluded from visible rows!
    pend_idx = win.status_filter_combo.findData("pending")
    win.status_filter_combo.setCurrentIndex(pend_idx)
    assert win.proxy_model.rowCount() == 3  # K1, K3, K4

    # Replace All in visible pending rows -> K1, K3 (preserving {velha}), K4; K2 stays untouched!
    replaced_cells = dlg.replace_all()
    assert replaced_cells == 3
    c1 = win.table_model.get_cell(0, 2)
    c3 = win.table_model.get_cell(2, 2)
    c4 = win.table_model.get_cell(3, 2)
    assert c1 is not None and c1.local_value == "Antiga espada"
    assert c2.local_value == "Velha armadura"  # filtered out, untouched
    assert c3 is not None and c3.local_value == "Antiga {velha} bota"
    assert c4 is not None and c4.local_value == "Antiga capa"

    # Single Ctrl+Z undoes the entire Replace All batch
    win.undo_stack.undo()
    assert c1.local_value == "Velha espada"
    assert c3.local_value == "Velha {velha} bota"
    assert c4.local_value == "Velha capa"

    # Single Ctrl+Y redoes the entire batch
    win.undo_stack.redo()
    assert c1.local_value == "Antiga espada"
    assert c3.local_value == "Antiga {velha} bota"
    assert c4.local_value == "Antiga capa"

    dlg.close()
    win.close()
