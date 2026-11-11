import json
from pathlib import Path

from pytestqt.qtbot import QtBot

from app.ui.main_window import MainWindow


def _write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def test_main_window_opens_package_displays_columns_inspector_and_file_filter(
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    pkg = tmp_path / "ui-mod"
    _write_json(
        pkg / "module.json",
        {
            "id": "ui-mod",
            "languages": [
                {"lang": "en", "name": "English", "path": "lang/en.json"},
                {"lang": "en", "name": "English Extra", "path": "lang/extra-en.json"},
                {"lang": "pt-BR", "name": "Português", "path": "lang/pt-BR.json"},
                {"lang": "pt-BR", "name": "Português 2", "path": "lang/pt-BR-2.json", "system": "dnd5e"},
                {"lang": "es", "name": "Español", "path": "lang/es.json"},
            ],
        },
    )
    _write_json(pkg / "lang/en.json", {"UI": {"Title": "Title", "Empty": "Empty"}})
    _write_json(pkg / "lang/extra-en.json", {"EXTRA": {"Msg": "Extra"}})
    _write_json(pkg / "lang/pt-BR.json", {"UI": {"Title": "Título antigo", "Empty": ""}, "OLD": {"X": "Velha"}})
    _write_json(pkg / "lang/pt-BR-2.json", {"UI": {"Title": "Título"}})
    # Arquivo malformado em es não deve travar o resto da tabela
    (pkg / "lang/es.json").write_text('{"UI": {"Title": "Título", ', encoding="utf-8")

    win = MainWindow()
    qtbot.addWidget(win)
    win.open_package_manifest(pkg / "module.json")

    model = win.table_model
    assert model.columnCount() == 4  # KEY_PATH, en (Base), pt-BR, es
    assert model.headerData(0, win.table.horizontalHeader().orientation()) == "KEY_PATH"
    assert "en" in str(model.headerData(1, win.table.horizontalHeader().orientation()))
    assert "pt-BR" in str(model.headerData(2, win.table.horizontalHeader().orientation()))
    assert "system: dnd5e" in str(model.headerData(2, win.table.horizontalHeader().orientation()))

    # Deve ter 4 linhas (UI.Title, UI.Empty, EXTRA.Msg, OLD.X)
    assert win.proxy_model.rowCount() == 4

    # Ocultar coluna 'es' via checkbox na toolbar
    es_checkbox = win.lang_checkboxes["es"]
    es_checkbox.setChecked(False)
    assert win.table.isColumnHidden(3) is True
    es_checkbox.setChecked(True)
    assert win.table.isColumnHidden(3) is False

    # Selecionar célula EXTRA.Msg em pt-BR (missing) e conferir atualização do Inspector (inclui condição)
    extra_row = next(i for i, r in enumerate(model.rows) if r.key_path == "EXTRA.Msg")
    win.table.setCurrentIndex(win.proxy_model.index(extra_row, 2))
    assert "EXTRA.Msg" in win.inspector_key_label.text()
    assert "system: dnd5e" in win.inspector_key_label.text()
    assert "lang/extra-en.json" in win.inspector_origin_label.text()
    assert "MISSING" in win.inspector_state_label.text()

    # Selecionar célula UI.Title em pt-BR -> Inspector sinaliza colisão multi-arquivo
    title_row = next(i for i, r in enumerate(model.rows) if r.key_path == "UI.Title")
    win.table.setCurrentIndex(win.proxy_model.index(title_row, 2))
    assert "multi_file_collision" in win.inspector_diag_label.text()

    # Selecionar célula UI.Title em es -> Inspector aponta arquivo fatal + linha
    win.table.setCurrentIndex(win.proxy_model.index(title_row, 3))
    assert "es.json:1" in win.inspector_diag_label.text()

    # Filtro por arquivo na toolbar (lang/extra-en.json)
    idx = win.file_filter_combo.findData("lang/extra-en.json")
    assert idx >= 0
    win.file_filter_combo.setCurrentIndex(idx)
    assert win.proxy_model.rowCount() == 1

    # Banner de diagnóstico ativo devido ao es.json malformado + retração do Inspector
    assert win.diagnostic_banner.isHidden() is False
    assert "es.json" in win.diagnostic_banner.text()
    win.toggle_inspector_button.click()
    assert win.inspector_panel.isHidden() is True

    # Rodapé numérico preenchido
    assert "4 chaves" in win.statusBar().currentMessage()

