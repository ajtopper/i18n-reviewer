from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPalette, QTextDocument
from PySide6.QtWidgets import QApplication
from pytestqt.qtbot import QtBot

from app.core.project_manager import CellData, CellKind
from app.ui.delegates import StatusCellDelegate, _resolve_cell_style
from app.ui.highlighter import TokenHighlighter
from app.ui.main_window import MainWindow
from app.ui.theme import (
    DARK_TOKENS,
    LIGHT_TOKENS,
    ThemeManager,
    load_theme_preference,
    resolve_is_dark,
    save_theme_preference,
)


def test_resolve_is_dark_respects_mode_and_system_scheme() -> None:
    assert resolve_is_dark("light", Qt.ColorScheme.Dark) is False
    assert resolve_is_dark("dark", Qt.ColorScheme.Light) is True
    assert resolve_is_dark("auto", Qt.ColorScheme.Dark) is True
    assert resolve_is_dark("auto", Qt.ColorScheme.Light) is False


def test_theme_preference_roundtrip_preserves_other_settings(tmp_path: Path) -> None:
    settings_path = tmp_path / "settings.json"
    settings_path.write_text(json.dumps({"spell_ascii_dir": "C:/enchant"}), encoding="utf-8")

    assert load_theme_preference(tmp_path) == "auto"

    save_theme_preference(tmp_path, "dark")
    assert load_theme_preference(tmp_path) == "dark"
    raw = json.loads(settings_path.read_text(encoding="utf-8"))
    assert raw["spell_ascii_dir"] == "C:/enchant"
    assert raw["ui_theme"] == "dark"


def test_theme_manager_applies_fusion_palette_and_system_signal(qtbot: QtBot, tmp_path: Path) -> None:
    mgr = ThemeManager(app_data_dir=tmp_path)
    tokens = mgr.set_mode("dark")
    assert tokens == DARK_TOKENS

    app = QApplication.instance()
    assert isinstance(app, QApplication)
    assert app.palette().color(QPalette.ColorRole.Window).name().lower() == DARK_TOKENS.bg_surface
    assert DARK_TOKENS.bg_surface in app.styleSheet()

    # Switching back to auto responds to system scheme changes
    mgr.set_mode("auto")
    mgr._on_system_scheme_changed(Qt.ColorScheme.Light)
    # In auto mode, apply() reads current QGuiApplication.styleHints().colorScheme()
    assert mgr.tokens in (LIGHT_TOKENS, DARK_TOKENS)


def test_main_window_persists_and_restores_theme_choice(qtbot: QtBot, tmp_path: Path) -> None:
    win1 = MainWindow(app_data_dir=tmp_path)
    qtbot.addWidget(win1)
    idx_dark = win1.theme_combo.findData("dark")
    win1.theme_combo.setCurrentIndex(idx_dark)
    assert win1.theme_manager.mode == "dark"
    assert win1.theme_manager.tokens == DARK_TOKENS
    win1.close()

    win2 = MainWindow(app_data_dir=tmp_path)
    qtbot.addWidget(win2)
    assert win2.theme_manager.mode == "dark"
    assert win2.theme_combo.currentData() == "dark"
    assert win2.theme_manager.tokens == DARK_TOKENS
    win2.close()


def test_cell_style_and_highlighter_adapt_to_light_and_dark() -> None:
    reviewed = CellData(
        prod_value="Olá",
        local_value="Olá",
        kind=CellKind.TRANSLATED,
        review_status="reviewed",
    )
    stale = CellData(
        prod_value="Olá",
        local_value="Olá",
        kind=CellKind.TRANSLATED,
        review_status="stale",
    )
    light_bg, light_lbl, _ = _resolve_cell_style(reviewed, LIGHT_TOKENS)
    dark_bg, dark_lbl, _ = _resolve_cell_style(reviewed, DARK_TOKENS)
    assert light_lbl == "OK" and dark_lbl == "OK"
    assert light_bg != dark_bg

    stale_light_bg, stale_lbl, _ = _resolve_cell_style(stale, LIGHT_TOKENS)
    stale_dark_bg, _, _ = _resolve_cell_style(stale, DARK_TOKENS)
    assert stale_lbl == "STALE"
    assert stale_light_bg != stale_dark_bg

    doc = QTextDocument("Hello {name} <b>world</b>")
    hl = TokenHighlighter(doc, tokens=LIGHT_TOKENS)
    assert hl._formats["handlebars"].foreground().color().name().lower() == LIGHT_TOKENS.token_styles["handlebars"][0]
    hl.set_theme(DARK_TOKENS)
    assert hl._formats["handlebars"].foreground().color().name().lower() == DARK_TOKENS.token_styles["handlebars"][0]

    delegate = StatusCellDelegate(tokens=LIGHT_TOKENS)
    delegate.set_theme(DARK_TOKENS)
    assert delegate._tokens == DARK_TOKENS


def test_sidebar_context_bar_and_density_sync(qtbot: QtBot, tmp_path: Path) -> None:
    win = MainWindow(app_data_dir=tmp_path)
    qtbot.addWidget(win)
    win.show()

    assert win.context_count_badge.text() == "0 keys shown"
    assert win.context_breadcrumb_label.text() == "All files / All"

    win.sidebar_status_list.setCurrentRow(1)
    assert win.status_filter_combo.currentIndex() == 1
    assert win.context_breadcrumb_label.text() == "All files / Pending Only"

    win.btn_compact_density.setChecked(True)
    assert win.table.verticalHeader().minimumSectionSize() == 34

    win.toggle_sidebar_button.setChecked(False)
    assert not win.sidebar_panel.isVisible()
    win.close()
