from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication
from pytestqt.qtbot import QtBot

from app.ui.main_window import ExpandedEditorDialog, MainWindow
from app.ui.theme import (
    DEFAULT_ZOOM_FACTOR,
    MAX_ZOOM_FACTOR,
    MIN_ZOOM_FACTOR,
    ThemeManager,
    build_qss,
    clamp_zoom_factor,
    LIGHT_TOKENS,
    load_zoom_preference,
    save_zoom_preference,
)


def _write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def test_zoom_preference_roundtrip_and_clamping(tmp_path: Path) -> None:
    assert clamp_zoom_factor(0.2) == MIN_ZOOM_FACTOR
    assert clamp_zoom_factor(5.0) == MAX_ZOOM_FACTOR
    assert clamp_zoom_factor(float("nan")) == DEFAULT_ZOOM_FACTOR

    settings_path = tmp_path / "settings.json"
    settings_path.write_text(json.dumps({"ui_theme": "dark"}), encoding="utf-8")

    assert load_zoom_preference(tmp_path) == DEFAULT_ZOOM_FACTOR
    save_zoom_preference(tmp_path, 1.4)
    assert load_zoom_preference(tmp_path) == 1.4

    raw = json.loads(settings_path.read_text(encoding="utf-8"))
    assert raw["ui_theme"] == "dark"
    assert raw["ui_zoom"] == 1.4

    qss_100 = build_qss(LIGHT_TOKENS, zoom=1.0)
    qss_150 = build_qss(LIGHT_TOKENS, zoom=1.5)
    assert "font-size: 13px;" in qss_100
    assert "font-size: 20px;" in qss_150


def test_main_window_zoom_shortcuts_persistence_and_proportional_scaling(
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    pkg = tmp_path / "zoom-mod"
    _write_json(
        pkg / "module.json",
        {
            "id": "zoom-mod",
            "languages": [
                {"lang": "en", "path": "lang/en.json"},
                {"lang": "pt-BR", "path": "lang/pt-BR.json"},
            ],
        },
    )
    _write_json(pkg / "lang/en.json", {"UI": {"Long": "Line one\nLine two\nLine three\nLine four"}})
    _write_json(pkg / "lang/pt-BR.json", {"UI": {"Long": "Linha um\nLinha dois\nLinha três\nLinha quatro"}})

    app_data = tmp_path / "appdata"
    win = MainWindow(app_data_dir=app_data)
    qtbot.addWidget(win)
    win.open_package_manifest(pkg / "module.json")
    win.show()
    qtbot.waitExposed(win)

    assert win.theme_manager.zoom == 1.0
    assert win.zoom_status_button.text() == "Zoom: 100%"
    base_min_h = win.table.verticalHeader().minimumSectionSize()
    base_col0_w = win.table.columnWidth(0)
    base_badge_h = win.cell_delegate.badge_strip_height()
    base_key_font = win.table_model.data(win.table_model.index(0, 0), Qt.ItemDataRole.FontRole)
    assert isinstance(base_key_font, QFont)

    # Ctrl+= zooms in (110%), Ctrl++ zooms in again (120%)
    qtbot.keyClick(win.table, Qt.Key.Key_Equal, Qt.KeyboardModifier.ControlModifier)
    assert win.theme_manager.zoom == 1.1
    qtbot.keyClick(win.table, Qt.Key.Key_Plus, Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier)
    assert win.theme_manager.zoom == 1.2
    assert win.zoom_status_button.text() == "Zoom: 120%"

    app = QApplication.instance()
    assert isinstance(app, QApplication)
    assert "font-size: 16px;" in app.styleSheet()

    # Proportional table, delegate, column width, and key font scaling
    assert win.table.verticalHeader().minimumSectionSize() > base_min_h
    assert win.table.columnWidth(0) > base_col0_w
    assert win.cell_delegate.badge_strip_height() > base_badge_h
    scaled_key_font = win.table_model.data(win.table_model.index(0, 0), Qt.ItemDataRole.FontRole)
    assert isinstance(scaled_key_font, QFont)
    assert scaled_key_font.pointSize() > base_key_font.pointSize()

    # Compact mode scales proportionally with zoom
    win.btn_compact_density.setChecked(True)
    compact_zoomed_min = win.table.verticalHeader().minimumSectionSize()
    assert compact_zoomed_min == win.cell_delegate.min_row_height()
    assert compact_zoomed_min > 34
    win.btn_compact_density.setChecked(False)

    # Responsive panel bounds stay within window width even at max zoom
    win.theme_manager.set_zoom(MAX_ZOOM_FACTOR)
    win.resize(1000, 700)
    assert win.sidebar_panel.maximumWidth() + win.inspector_panel.maximumWidth() < win.width()

    # Ctrl+- steps down and Ctrl+0 resets to 100%
    qtbot.keyClick(win.table, Qt.Key.Key_Minus, Qt.KeyboardModifier.ControlModifier)
    assert win.theme_manager.zoom == 1.9
    qtbot.keyClick(win.table, Qt.Key.Key_0, Qt.KeyboardModifier.ControlModifier)
    assert win.theme_manager.zoom == 1.0
    assert win.zoom_status_button.text() == "Zoom: 100%"

    # Zoom persists across restarts
    win.theme_manager.set_zoom(1.3)
    win.close()

    win2 = MainWindow(app_data_dir=app_data)
    qtbot.addWidget(win2)
    assert win2.theme_manager.zoom == 1.3
    assert win2.zoom_status_button.text() == "Zoom: 130%"

    # ExpandedEditorDialog inherits zoom and accepts Ctrl++ / Ctrl+0
    dlg = ExpandedEditorDialog(
        "Hello",
        "Olá",
        "UI.Long",
        "pt-BR",
        win2,
        theme_manager=win2.theme_manager,
    )
    qtbot.addWidget(dlg)
    assert dlg.width() > 820
    qtbot.keyClick(dlg, Qt.Key.Key_Equal, Qt.KeyboardModifier.ControlModifier)
    assert win2.theme_manager.zoom == 1.4
    win2.close()
