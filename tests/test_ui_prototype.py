from __future__ import annotations

import pytest
from pytestqt.qtbot import QtBot

from scripts.ui_prototype import DARK_TOKENS, LIGHT_TOKENS, PrototypeWindow


def test_prototype_live_theme_switching_and_filters(qtbot: QtBot) -> None:
    win = PrototypeWindow()
    qtbot.addWidget(win)
    win.show()

    assert win.ctx_count_pill.text() == "6 keys shown"
    assert win.ins_key.text() == "HEAVYLORE.Material.rough-leather"

    # Switch through every available theme cleanly
    for idx in range(win.theme_combo.count()):
        theme_name = win.theme_combo.itemText(idx)
        win.theme_combo.setCurrentIndex(idx)
        assert win.status_theme_lbl.text() == f"Theme: {theme_name}"
        if "Dark" in theme_name:
            assert win._tokens == DARK_TOKENS
        elif "Light" in theme_name:
            assert win._tokens == LIGHT_TOKENS

    # Filter via sidebar file list and search box
    win.file_list.setCurrentRow(2)  # dialogues_act_1.json
    assert win.ctx_count_pill.text() == "2 keys shown"
    win.search_input.setText("Archivist")
    assert win.ctx_count_pill.text() == "1 keys shown"

    # Toggle sidebar visibility
    win.btn_sidebar.setChecked(False)
    assert not win.sidebar.isVisible()

