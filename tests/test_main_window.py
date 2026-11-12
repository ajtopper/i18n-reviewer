import json
from pathlib import Path
import time

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMessageBox, QStyleOptionViewItem
from pytestqt.qtbot import QtBot

from app.core.project_manager import CellData, CellKind, PackageSession, TableRowData, discover_manifest
from app.ui.main_window import ExpandedEditorDialog, MainWindow


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
    assert "4 keys" in win.statusBar().currentMessage()


def test_ticket02_editing_status_filters_search_undo_shortcuts_and_orphan_removal(
    qtbot: QtBot,
    tmp_path: Path,
    monkeypatch: object,
) -> None:
    pkg = tmp_path / "edit-mod"
    _write_json(
        pkg / "module.json",
        {
            "id": "edit-mod",
            "languages": [
                {"lang": "en", "name": "English", "path": "lang/en.json"},
                {"lang": "pt-BR", "name": "Português", "path": "lang/pt-BR.json"},
            ],
        },
    )
    _write_json(
        pkg / "lang/en.json",
        {
            "K1": "Hello",
            "K2": "World",
            "K3": "Missing key",
        },
    )
    _write_json(
        pkg / "lang/pt-BR.json",
        {
            "K1": "Olá",
            "K2": "Mundo",
            "OLD": "Órfã antiga",
        },
    )

    win = MainWindow()
    qtbot.addWidget(win)
    win.open_package_manifest(pkg / "module.json")

    model = win.table_model
    proxy = win.proxy_model

    # 1) Editar K1 inline (via setData) -> vira EDITADO (is_dirty=True, unreviewed) e entra no QUndoStack
    idx_k1 = proxy.index(0, 2)
    assert bool(model.flags(proxy.mapToSource(idx_k1)) & Qt.ItemFlag.ItemIsEditable) is True
    assert proxy.setData(idx_k1, "Oi", Qt.ItemDataRole.EditRole) is True
    c1 = model.get_cell(0, 2)
    assert c1 is not None and c1.local_value == "Oi" and c1.is_dirty is True and c1.review_status == "unreviewed"

    # Ctrl+Z desfaz e Ctrl+Y refaz
    win.undo_stack.undo()
    assert c1.local_value == "Olá" and c1.is_dirty is False
    win.undo_stack.redo()
    assert c1.local_value == "Oi" and c1.is_dirty is True

    # 2) Marcar K1 como revisado com Ctrl+Enter -> vira reviewed + mantém dirty (EDITADO · OK) e pula para K2
    win.table.setCurrentIndex(idx_k1)
    win.review_and_advance()
    assert c1.review_status == "reviewed" and c1.is_dirty is True
    cur_src = proxy.mapToSource(win.table.currentIndex())
    assert model.rows[cur_src.row()].key_path == "K2"

    # Ctrl+Down pula para próxima pendente (K3) sem alterar K2
    win.jump_to_next_pending()
    cur_src = proxy.mapToSource(win.table.currentIndex())
    assert model.rows[cur_src.row()].key_path == "K3"
    c2 = model.get_cell(1, 2)
    assert c2 is not None and c2.review_status == "unreviewed"

    # 3) Filtros: Apenas Editadas -> só K1; Apenas Pendentes -> K2, K3, OLD
    edit_idx = win.status_filter_combo.findData("edited")
    assert edit_idx >= 0
    win.status_filter_combo.setCurrentIndex(edit_idx)
    assert proxy.rowCount() == 1
    assert model.rows[proxy.mapToSource(proxy.index(0, 0)).row()].key_path == "K1"

    pend_idx = win.status_filter_combo.findData("pending")
    assert pend_idx >= 0
    win.status_filter_combo.setCurrentIndex(pend_idx)
    pend_keys = {model.rows[proxy.mapToSource(proxy.index(r, 0)).row()].key_path for r in range(proxy.rowCount())}
    assert pend_keys == {"K2", "K3", "OLD"}

    all_idx = win.status_filter_combo.findData("all")
    win.status_filter_combo.setCurrentIndex(all_idx)

    # 4) Busca com debounce 150ms
    win.search_input.setText("Mundo")
    qtbot.waitUntil(lambda: proxy.rowCount() == 1, timeout=1000)
    assert model.rows[proxy.mapToSource(proxy.index(0, 0)).row()].key_path == "K2"
    win.search_input.clear()
    qtbot.waitUntil(lambda: proxy.rowCount() == 4, timeout=1000)

    # 5) Reverter K1 para produção via comando Undoable
    win.table.setCurrentIndex(proxy.index(0, 2))
    win.revert_current_cell()
    assert c1.local_value == "Olá" and c1.is_dirty is False
    win.undo_stack.undo()
    assert c1.local_value == "Oi" and c1.is_dirty is True

    # 6) Marcar órfã OLD para remoção com confirmação explícita
    old_row = next(i for i, r in enumerate(model.rows) if r.key_path == "OLD")
    win.table.setCurrentIndex(proxy.index(old_row, 2))
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **kw: QMessageBox.StandardButton.Yes)  # type: ignore[attr-defined]
    win.toggle_orphan_deletion_current_cell()
    c_old = model.get_cell(old_row, 2)
    assert c_old is not None and c_old.marked_for_deletion is True and c_old.is_dirty is True
    win.undo_stack.undo()
    assert c_old.marked_for_deletion is False

    # 7) Editor expandido integrado com QUndoStack + atalhos reais Ctrl+Z / Ctrl+Y / Ctrl+F / Ctrl+Down
    win.show()
    qtbot.waitExposed(win)
    win.activateWindow()
    win.table.setFocus()
    win.table.setCurrentIndex(proxy.index(0, 2))
    monkeypatch.setattr(ExpandedEditorDialog, "exec", lambda self: ExpandedEditorDialog.DialogCode.Accepted)
    monkeypatch.setattr(ExpandedEditorDialog, "edited_text", lambda self: "Olá expandido")
    qtbot.keyClick(win.table, Qt.Key.Key_F2, Qt.KeyboardModifier.ShiftModifier)
    assert c1.local_value == "Olá expandido"

    qtbot.keyClick(win.table, Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier)
    assert c1.local_value == "Oi"
    qtbot.keyClick(win.table, Qt.Key.Key_Y, Qt.KeyboardModifier.ControlModifier)
    assert c1.local_value == "Olá expandido"

    # Ctrl+F foca o campo de busca
    qtbot.keyClick(win.table, Qt.Key.Key_F, Qt.KeyboardModifier.ControlModifier)
    qtbot.waitUntil(win.search_input.hasFocus, timeout=500)


def test_ticket02_pending_filter_includes_stale_empty_and_jumps_across_columns(
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    pkg = tmp_path / "multi-pending"
    _write_json(
        pkg / "module.json",
        {
            "id": "multi-pending",
            "languages": [
                {"lang": "en", "path": "lang/en.json"},
                {"lang": "pt-BR", "path": "lang/pt-BR.json"},
                {"lang": "es", "path": "lang/es.json"},
            ],
        },
    )
    _write_json(pkg / "lang/en.json", {"A": "One", "B": "Two"})
    _write_json(pkg / "lang/pt-BR.json", {"A": "Um", "B": "Dois"})
    _write_json(pkg / "lang/es.json", {"A": "", "B": "Dos"})

    win = MainWindow()
    qtbot.addWidget(win)
    win.open_package_manifest(pkg / "module.json")

    # Marca pt-BR inteiro como reviewed (sem pendentes em pt-BR), B em es também reviewed;
    # A em pt-BR fica stale e A em es tem string vazia ""
    c_pt_a = win.table_model.get_cell(0, 2)
    c_pt_b = win.table_model.get_cell(1, 2)
    c_es_b = win.table_model.get_cell(1, 3)
    assert c_pt_a and c_pt_b and c_es_b
    c_pt_a.review_status = "stale"
    c_pt_b.mark_reviewed()
    c_es_b.mark_reviewed()

    pend_idx = win.status_filter_combo.findData("pending")
    win.status_filter_combo.setCurrentIndex(pend_idx)
    assert win.proxy_model.rowCount() == 1  # Apenas linha A (stale em pt-BR e "" em es)

    # Sem pendentes em pt-BR após aprovar A em pt-BR -> jump_to_next_pending salta para coluna es!
    c_pt_a.mark_reviewed()
    win.table.setCurrentIndex(win.proxy_model.index(0, 2))
    win.jump_to_next_pending()
    assert win.table.currentIndex().column() == 3


def test_ticket03_save_open_unsaved_star_recovery_watcher_conflict_and_stale_inspector(
    qtbot: QtBot,
    tmp_path: Path,
    monkeypatch: object,
) -> None:
    from app.core.project_manager import ConflictResolution, write_recovery_draft
    from app.ui.conflict_dialog import ConflictResolutionDialog

    app_data = tmp_path / "appdata"
    pkg = tmp_path / "proj-mod"
    _write_json(
        pkg / "module.json",
        {
            "id": "proj-mod",
            "languages": [
                {"lang": "en", "path": "lang/en.json"},
                {"lang": "pt-BR", "path": "lang/pt-BR.json"},
            ],
        },
    )
    _write_json(pkg / "lang/en.json", {"K1": "One", "K2": "Two"})
    _write_json(pkg / "lang/pt-BR.json", {"K1": "Um", "K2": "Dois", "DEL_CONFLICT": "Velha"})

    win = MainWindow(app_data_dir=app_data)
    qtbot.addWidget(win)
    win.open_package_manifest(pkg / "module.json")
    assert "*" not in win.windowTitle()

    # Editar marca projeto com '*' e grava recovery draft; marca DEL_CONFLICT para remoção
    assert win.proxy_model.setData(win.proxy_model.index(0, 2), "Um editado", Qt.ItemDataRole.EditRole) is True
    assert "*" in win.windowTitle()
    win.mark_current_reviewed()  # K1 reviewed, K2 still unreviewed
    c_del = win.table_model.get_cell(2, 2)
    assert c_del is not None
    c_del.set_marked_for_deletion(True)

    proj_file = tmp_path / "proj-mod.i18nproj"
    win.save_project(proj_file)
    assert "*" not in win.windowTitle()
    assert proj_file.exists()
    old_hash = win.session.file_snapshots["lang/pt-BR.json"].sha256 if win.session else ""

    # Simula mudança externa no disco enquanto app está aberto: K1 muda base, K1 e DEL_CONFLICT conflitam
    _write_json(pkg / "lang/en.json", {"K1": "One updated", "K2": "Two"})
    _write_json(pkg / "lang/pt-BR.json", {"K1": "Um do disco", "K2": "Dois", "DEL_CONFLICT": "Velha atualizada"})

    win.check_for_external_changes()
    assert win.external_change_banner.isHidden() is False

    # Cancelar o diálogo de conflito NÃO deve atualizar o snapshot nem ocultar o banner
    monkeypatch.setattr(
        ConflictResolutionDialog,
        "exec",
        lambda self: ConflictResolutionDialog.DialogCode.Rejected,
    )
    win.sync_with_disk()
    assert win.external_change_banner.isHidden() is False
    assert win.session is not None
    assert win.session.file_snapshots["lang/pt-BR.json"].sha256 == old_hash

    # Confirmar resolução: aceitar do disco em K1 e editar manualmente DEL_CONFLICT (estava marked_for_deletion=True)
    monkeypatch.setattr(
        ConflictResolutionDialog,
        "exec",
        lambda self: ConflictResolutionDialog.DialogCode.Accepted,
    )
    monkeypatch.setattr(
        ConflictResolutionDialog,
        "resolutions",
        lambda self: [
            ConflictResolution(key_path="K1", lang="pt-BR", choice="accept_disk", manual_value="Um do disco"),
            ConflictResolution(key_path="DEL_CONFLICT", lang="pt-BR", choice="manual", manual_value="Resolvida manual"),
        ],
    )
    win.sync_with_disk()
    assert win.external_change_banner.isHidden() is True
    c1 = win.table_model.get_cell(0, 2)
    c_del_after = win.table_model.get_cell(2, 2)
    assert c1 is not None and c1.local_value == "Um do disco" and c1.is_dirty is False
    assert c_del_after is not None and c_del_after.marked_for_deletion is False and c_del_after.local_value == "Resolvida manual"

    # Reabre com crash recovery pendente e verifica exibição stale no Inspector
    assert win.session is not None
    c1.review_status = "stale"
    c1.previous_base = "One"
    win._on_current_changed(win.proxy_model.index(0, 2), win.proxy_model.index(0, 2))
    assert win.inspector_stale_label.isHidden() is False
    assert "Before: One" in win.inspector_stale_label.text()
    assert "Now:" in win.inspector_stale_label.text()

    # Grava recovery simulando fechamento inesperado e aceita restaurar ao reabrir
    c2 = win.table_model.get_cell(1, 2)
    assert c2 is not None
    c2.apply_edit("Dois crash recovery", base_text="Two")
    write_recovery_draft(win.session, app_data_dir=app_data)

    monkeypatch.setattr(QMessageBox, "question", lambda *a, **kw: QMessageBox.StandardButton.Yes)  # type: ignore[attr-defined]
    win2 = MainWindow(app_data_dir=app_data)
    qtbot.addWidget(win2)
    win2.open_project_file(proj_file)
    c2_reopened = win2.table_model.get_cell(1, 2)
    assert c2_reopened is not None and c2_reopened.local_value == "Dois crash recovery"


def test_ticket04_publish_dialog_and_backup_dialog_flow(
    qtbot: QtBot,
    tmp_path: Path,
    monkeypatch: object,
) -> None:
    from app.core.project_manager import ConflictResolution
    from app.ui.backup_dialog import BackupDialog, PublishDialog, RestoreSelection
    from app.ui.conflict_dialog import ConflictResolutionDialog

    app_data = tmp_path / "appdata"
    pkg = tmp_path / "ui-pub-mod"
    _write_json(
        pkg / "module.json",
        {
            "id": "ui-pub-mod",
            "languages": [
                {"lang": "en", "path": "lang/en.json"},
                {"lang": "pt-BR", "path": "lang/pt-BR.json"},
                {"lang": "es", "path": "lang/es.json"},
            ],
        },
    )
    _write_json(pkg / "lang/en.json", {"A": "One"})
    _write_json(pkg / "lang/pt-BR.json", {"A": "Um v1"})
    _write_json(pkg / "lang/es.json", {"A": "Uno v1"})

    win = MainWindow(app_data_dir=app_data)
    qtbot.addWidget(win)
    win.open_package_manifest(pkg / "module.json")

    assert win.proxy_model.setData(win.proxy_model.index(0, 2), "Um v2", Qt.ItemDataRole.EditRole) is True
    assert win.proxy_model.setData(win.proxy_model.index(0, 3), "Uno v2", Qt.ItemDataRole.EditRole) is True

    # Publica apenas pt-BR desmarcando es no PublishDialog
    monkeypatch.setattr(PublishDialog, "exec", lambda self: PublishDialog.DialogCode.Accepted)
    monkeypatch.setattr(
        PublishDialog,
        "selected_plans",
        lambda self: [fp for fp in self.plan.file_plans if fp.lang == "pt-BR"],
    )
    win.publish_to_production()

    assert json.loads((pkg / "lang/pt-BR.json").read_text(encoding="utf-8")) == {"A": "Um v2"}
    assert json.loads((pkg / "lang/es.json").read_text(encoding="utf-8")) == {"A": "Uno v1"}
    c_pt = win.table_model.get_cell(0, 2)
    c_es = win.table_model.get_cell(0, 3)
    assert c_pt is not None and c_pt.is_dirty is False
    assert c_es is not None and c_es.is_dirty is True

    # Novo rascunho em pt-BR + restauração sem descartar rascunhos abre ConflictResolutionDialog
    assert win.proxy_model.setData(win.proxy_model.index(0, 2), "Um v3 draft", Qt.ItemDataRole.EditRole) is True
    dlg = BackupDialog(win.session.project_id if win.session else "", app_data_dir=app_data, parent=win)
    qtbot.addWidget(dlg)
    assert dlg.batch_list.count() == 1
    assert dlg.selected_batch() is not None
    first_batch_id = dlg.selected_batch().batch_id  # type: ignore[union-attr]

    monkeypatch.setattr(BackupDialog, "exec", lambda self: BackupDialog.DialogCode.Accepted)
    monkeypatch.setattr(
        BackupDialog,
        "restore_choice",
        lambda self: RestoreSelection(batch_id=first_batch_id, rel_paths=None, discard_local_drafts=False),
    )
    monkeypatch.setattr(ConflictResolutionDialog, "exec", lambda self: ConflictResolutionDialog.DialogCode.Accepted)
    monkeypatch.setattr(
        ConflictResolutionDialog,
        "resolutions",
        lambda self: [ConflictResolution(key_path="A", lang="pt-BR", choice="accept_disk", manual_value="Um v1")],
    )
    win.open_backup_dialog()
    assert json.loads((pkg / "lang/pt-BR.json").read_text(encoding="utf-8")) == {"A": "Um v1"}
    c_pt_after = win.table_model.get_cell(0, 2)
    assert c_pt_after is not None and c_pt_after.local_value == "Um v1"
    win.save_project(tmp_path / "ui-pub-mod.i18nproj")




def test_ticket02_row_height_cap_and_10k_scale(qtbot: QtBot, tmp_path: Path) -> None:
    pkg = tmp_path / "scale-mod"
    _write_json(pkg / "module.json", {"id": "scale-mod", "languages": [{"lang": "en", "path": "lang/en.json"}]})
    _write_json(pkg / "lang/en.json", {"A": "One"})
    manifest = discover_manifest(pkg / "module.json")

    rows: list[TableRowData] = []
    for i in range(10000):
        long_text = "Linha longa " + ("palavra " * 40) if i == 0 else f"Value {i}"
        rows.append(
            TableRowData(
                key_path=f"MOD.Key{i}",
                base_text=f"Base {i}",
                cells={"pt-BR": CellData(prod_value=long_text, local_value=long_text, kind=CellKind.TRANSLATED)},
            )
        )
    session = PackageSession(
        manifest=manifest,
        base_lang="en",
        base_external_path=None,
        target_langs=["pt-BR"],
        files=[],
        rows=rows,
        warnings=[],
    )

    win = MainWindow()
    qtbot.addWidget(win)
    t0 = time.perf_counter()
    win.load_session(session)
    win.search_input.setText("Key9999")
    qtbot.waitUntil(lambda: win.proxy_model.rowCount() == 1, timeout=1000)
    elapsed = time.perf_counter() - t0
    assert elapsed < 2.0

    # Confirma teto de altura (~110 px) para célula com texto gigante
    win.search_input.clear()
    qtbot.waitUntil(lambda: win.proxy_model.rowCount() == 10000, timeout=1000)
    delegate = win.table.itemDelegate()
    opt = QStyleOptionViewItem()
    opt.rect.setWidth(240)
    sz = delegate.sizeHint(opt, win.proxy_model.index(0, 2))
    assert sz.height() <= 115


def test_ticket05_validation_filter_highlighter_token_insert_ignore_and_custom_enrichers(
    qtbot: QtBot,
    tmp_path: Path,
    monkeypatch: object,
) -> None:
    from PySide6.QtGui import QSyntaxHighlighter
    from PySide6.QtWidgets import QInputDialog, QPlainTextEdit
    from app.core.validator import CustomEnricherRule
    from app.ui.main_window import ExpandedEditorDialog

    app_data = tmp_path / "appdata"
    pkg = tmp_path / "val-ui-mod"
    _write_json(
        pkg / "module.json",
        {
            "id": "val-ui-mod",
            "languages": [
                {"lang": "en", "path": "lang/en.json"},
                {"lang": "pt-BR", "path": "lang/pt-BR.json"},
            ],
        },
    )
    _write_json(
        pkg / "lang/en.json",
        {
            "OK_KEY": "Hello {name}",
            "PH_ERR": "Hello {name}",
            "URL_WARN": "Docs at https://foundryvtt.com",
            "BASE_COL": "Gain @UUID[Compendium.a.b]{power} for {power}",
        },
    )
    _write_json(
        pkg / "lang/pt-BR.json",
        {
            "OK_KEY": "Olá {name}",
            "PH_ERR": "Olá mundo",
            "URL_WARN": "Docs aqui",
            "BASE_COL": "Ganhe @UUID[Compendium.a.b]{poder} para {power}",
        },
    )

    win = MainWindow(app_data_dir=app_data)
    qtbot.addWidget(win)
    win.open_package_manifest(pkg / "module.json")

    # Validação inicial em QThreadPool termina populando alertas
    qtbot.waitUntil(lambda: not win.validation_in_progress, timeout=3000)

    c_err = win.table_model.get_cell(1, 2)
    c_warn = win.table_model.get_cell(2, 2)
    c_ok = win.table_model.get_cell(0, 2)
    r_col = win.table_model.get_row(3)
    assert c_err is not None and c_err.validation_severity == "critical"
    assert c_warn is not None and c_warn.validation_severity == "warning"
    assert c_ok is not None and c_ok.validation_severity is None
    assert r_col is not None and any(i.severity == "info" for i in r_col.base_issues)

    # Filtro "Todos os Alertas" exibe apenas linhas com erro crítico ou aviso ativo (PH_ERR e URL_WARN)
    alerts_idx = win.status_filter_combo.findData("alerts")
    assert alerts_idx >= 0
    win.status_filter_combo.setCurrentIndex(alerts_idx)
    assert win.proxy_model.rowCount() == 2
    win.status_filter_combo.setCurrentIndex(0)

    # Editor inline e ExpandedEditorDialog usam TokenHighlighter (QSyntaxHighlighter) e revalidam ao vivo
    idx_err = win.proxy_model.index(1, 2)
    win.table.setCurrentIndex(idx_err)
    editor = win.cell_delegate.createEditor(win.table, QStyleOptionViewItem(), idx_err)
    qtbot.addWidget(editor)
    assert isinstance(editor, QPlainTextEdit)
    assert editor.findChildren(QSyntaxHighlighter)
    win.cell_delegate.setEditorData(editor, idx_err)
    editor.setPlainText("Olá {name}")
    assert c_err.validation_severity is None
    editor.setPlainText("Olá mundo")
    assert c_err.validation_severity == "critical"

    exp = ExpandedEditorDialog("Hello {name}", "Olá mundo", "PH_ERR", "pt-BR", win)
    qtbot.addWidget(exp)
    assert exp.base_view.findChildren(QSyntaxHighlighter)
    assert exp.target_edit.findChildren(QSyntaxHighlighter)

    # Reinserção rápida de token faltante via Inspector/ação com QUndoStack + Undo/Redo
    assert win.insert_missing_token_for_current("{name}") is True
    assert c_err.local_value == "Olá mundo{name}" or "{name}" in (c_err.local_value or "")
    assert c_err.validation_severity is None  # Reavaliação síncrona limpou erro!

    win.undo_stack.undo()
    assert c_err.local_value == "Olá mundo"
    assert c_err.validation_severity == "critical"

    # Ignorar este alerta com justificativa -> limpa gravidade ativa e persiste no .i18nproj
    monkeypatch.setattr(QInputDialog, "getText", lambda *a, **kw: ("Intencional", True))  # type: ignore[attr-defined]
    assert win.toggle_ignore_warning_current("placeholder_mismatch") is True
    assert c_err.validation_severity is None

    # Aplicar regra customizada e salvar projeto
    assert win.session is not None
    win.session.custom_enrichers.append(CustomEnricherRule(name="MyTag", pattern=r"%[A-Z]+%"))
    proj_path = tmp_path / "val-ui.i18nproj"
    win.save_project(proj_path)


def test_ticket06_glossary_dialog_filter_ctrl_space_and_context_menu(
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    from PySide6.QtCore import QEvent
    from PySide6.QtGui import QKeyEvent
    from PySide6.QtWidgets import QListWidget, QPlainTextEdit
    from app.core.glossary import GlossaryEntry, save_global_glossary
    from app.ui.glossary_dialog import GlossaryDialog
    from app.ui.main_window import ExpandedEditorDialog

    app_data = tmp_path / "appdata"
    save_global_glossary(
        [GlossaryEntry(term="Spell", translations={"pt-BR": ["Magia"]})],
        app_data_dir=app_data,
    )

    pkg = tmp_path / "gloss-ui-mod"
    _write_json(
        pkg / "module.json",
        {
            "id": "gloss-ui-mod",
            "languages": [
                {"lang": "en", "path": "lang/en.json"},
                {"lang": "pt-BR", "path": "lang/pt-BR.json"},
            ],
        },
    )
    _write_json(
        pkg / "lang/en.json",
        {
            "CAST": "Cast a Spell",
            "EMPTY_KEY": "Spend a Spell",
            "CLEAN": "Hello",
        },
    )
    _write_json(
        pkg / "lang/pt-BR.json",
        {
            "CAST": "Conjure uma bênção",
            "CLEAN": "Olá",
        },
    )

    win = MainWindow(app_data_dir=app_data)
    qtbot.addWidget(win)
    win.open_package_manifest(pkg / "module.json")
    assert win.session is not None
    # Projeto sobrescreve "Spell" para "Feitiço"
    win.session.project_glossary = [
        GlossaryEntry(term="Spell", translations={"pt-BR": ["Feitiço", "Feitiços"]})
    ]
    win.revalidate_session()
    qtbot.waitUntil(lambda: not win.validation_in_progress, timeout=3000)

    c_cast = win.table_model.get_cell(0, 2)
    c_empty = win.table_model.get_cell(1, 2)
    c_clean = win.table_model.get_cell(2, 2)
    assert c_cast is not None and c_cast.active_glossary_issues
    assert c_empty is not None and c_empty.active_glossary_issues == []  # missing não dispara alerta
    assert c_clean is not None and c_clean.active_glossary_issues == []

    # Filtro "Inconsistências de Glossário" exibe apenas CAST
    gloss_idx = win.status_filter_combo.findData("glossary")
    assert gloss_idx >= 0
    win.status_filter_combo.setCurrentIndex(gloss_idx)
    assert win.proxy_model.rowCount() == 1
    win.status_filter_combo.setCurrentIndex(0)

    # Ctrl+Space no editor inline abre popup e insere tradução preferida no cursor
    idx_empty = win.proxy_model.index(1, 2)
    win.table.setCurrentIndex(idx_empty)
    editor = win.cell_delegate.createEditor(win.table, QStyleOptionViewItem(), idx_empty)
    qtbot.addWidget(editor)
    assert isinstance(editor, QPlainTextEdit)
    win.cell_delegate.setEditorData(editor, idx_empty)
    editor.setPlainText("Gaste ")
    cursor = editor.textCursor()
    cursor.setPosition(len("Gaste "))
    editor.setTextCursor(cursor)
    ev = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Space, Qt.KeyboardModifier.ControlModifier)
    from PySide6.QtWidgets import QApplication
    QApplication.sendEvent(editor, ev)
    popup = editor.findChild(QListWidget)
    assert popup is not None and popup.count() >= 1
    first_item = popup.item(0)
    assert first_item is not None
    popup.itemActivated.emit(first_item)
    assert "Feitiço" in editor.toPlainText()

    # Ctrl+Space também funciona no ExpandedEditorDialog
    exp = ExpandedEditorDialog(
        "Cast a Spell",
        "Lance ",
        "CAST",
        "pt-BR",
        win,
        glossary_entries=win.merged_glossary(),
    )
    qtbot.addWidget(exp)
    c2 = exp.target_edit.textCursor()
    c2.setPosition(len("Lance "))
    exp.target_edit.setTextCursor(c2)
    ev2 = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Space, Qt.KeyboardModifier.ControlModifier)
    QApplication.sendEvent(exp.target_edit, ev2)
    popup2 = exp.target_edit.findChild(QListWidget)
    assert popup2 is not None and popup2.count() >= 1
    popup2.itemActivated.emit(popup2.item(0))  # type: ignore[arg-type]
    assert "Feitiço" in exp.target_edit.toPlainText()
    # ExpandedEditorDialog exibe alerta de glossário em tempo real ao remover o termo preferido
    exp.target_edit.setPlainText("Conjure uma bênção")
    assert "Spell" in exp.live_alert_label.text()

    # Ctrl+Space direto na célula vazia da tabela (sem editor aberto) preenche via QUndoStack
    win.table.setCurrentIndex(idx_empty)
    ev_tbl = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Space, Qt.KeyboardModifier.ControlModifier)
    QApplication.sendEvent(win.table, ev_tbl)
    tbl_popup = win.table.findChild(QListWidget)
    assert tbl_popup is not None and tbl_popup.count() >= 1
    tbl_popup.itemActivated.emit(tbl_popup.item(0))  # type: ignore[arg-type]
    assert c_empty.local_value == "Feitiço"

    # GlossaryDialog pré-preenchido, preservação de idiomas não exibidos, case-sensitive e deduplicação CSV
    gdlg = GlossaryDialog(
        global_entries=[GlossaryEntry(term="Spell", translations={"pt-BR": ["Magia"]})],
        project_entries=[
            GlossaryEntry(term="HP", case_sensitive=True, do_not_translate=True),
            GlossaryEntry(term="Cantrip", translations={"pt-BR": ["Truque antigo"], "fr": ["Tour"]}),
        ],
        target_langs=["pt-BR"],
        prefill_term="Cantrip",
        prefill_translation="Truque",
        prefill_lang="pt-BR",
        parent=win,
    )
    qtbot.addWidget(gdlg)
    assert gdlg.term_input.text() == "Cantrip"
    gdlg.save_form_entry()
    cantrip = next(e for e in gdlg.project_entries() if e.term == "Cantrip")
    assert cantrip.translations == {"pt-BR": ["Truque"], "fr": ["Tour"]}

    # Adicionar entrada "hp" case_sensitive=True não sobrescreve "HP"
    gdlg.term_input.setText("hp")
    gdlg.case_cb.setChecked(True)
    gdlg.dnt_cb.setChecked(True)
    gdlg.save_form_entry()
    terms = {e.term for e in gdlg.project_entries()}
    assert {"HP", "hp"} <= terms

    win.save_project(tmp_path / "gloss-ui.i18nproj")


def test_ticket07_spellcheck_batch_on_demand_suggest_missing_lang_and_pwl(
    qtbot: QtBot,
    tmp_path: Path,
    monkeypatch: object,
) -> None:
    app_data = tmp_path / "appdata"
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
    _write_json(pkg / "lang/en.json", {"S1": "Spell failed", "S2": "Custom term", "S3": "Another custom term"})
    _write_json(pkg / "lang/pt-BR.json", {"S1": "O feitisso falhou", "S2": "Palavra Zorgxp", "S3": "Mesma Zorgxp aqui"})
    _write_json(pkg / "lang/eo.json", {"S1": "Xyzqwerty", "S2": "Abcdefg", "S3": "Hijklm"})

    win = MainWindow(app_data_dir=app_data)
    qtbot.addWidget(win)

    suggest_calls: list[str] = []
    orig_suggest = win.spell_service.suggest

    def _spy_suggest(lang: str, word: str, limit: int = 6) -> list[str]:
        suggest_calls.append(f"{lang}:{word}")
        return orig_suggest(lang, word, limit=limit)

    monkeypatch.setattr(win.spell_service, "suggest", _spy_suggest)  # type: ignore[attr-defined]
    win.open_package_manifest(pkg / "module.json")
    qtbot.waitUntil(lambda: not win.validation_in_progress, timeout=4000)

    # Batch nunca chama suggest()
    assert suggest_calls == []

    # pt-BR detecta erros de ortografia; eo sem dicionário fica desligado + aviso no cabeçalho/Inspector
    c_s1_pt = win.table_model.get_cell(0, 2)
    c_s1_eo = win.table_model.get_cell(0, 3)
    c_s2_pt = win.table_model.get_cell(1, 2)
    c_s3_pt = win.table_model.get_cell(2, 2)
    assert c_s1_pt is not None and any(i.rule_id == "spell:feitisso" for i in c_s1_pt.active_spell_issues)
    assert c_s1_pt.validation_severity == "warning"
    assert c_s1_eo is not None and c_s1_eo.active_spell_issues == []

    hdr_eo = str(win.table_model.headerData(3, Qt.Orientation.Horizontal))
    assert "no spellcheck" in hdr_eo.lower()
    win.table.setCurrentIndex(win.proxy_model.index(0, 3))
    assert "hunspell" in win.inspector_diag_label.text().lower()

    # Menu de contexto (4ª seção) calcula suggest() sob demanda e permite corrigir / adicionar ao dicionário
    win.table.setCurrentIndex(win.proxy_model.index(0, 2))
    assert any("feitisso" in s for s in suggest_calls)
    r0 = win.table_model.get_row(0)
    assert r0 is not None
    ctx_menu = win._build_cell_context_menu(r0, c_s1_pt, 2)
    action_texts = [a.text() for a in ctx_menu.actions() if not a.isSeparator()]
    assert any("Fix 'feitisso'" in t for t in action_texts)
    assert "Add 'feitisso' to dictionary" in action_texts

    # Substituição preserva spans técnicos caso palavra ocorra em URL/placeholder anterior
    assert win.proxy_model.setData(win.proxy_model.index(0, 2), "Veja {feitisso} o feitisso falhou", Qt.ItemDataRole.EditRole) is True
    assert win.replace_spell_word_for_current("feitisso", "feitiço") is True
    assert c_s1_pt.local_value == "Veja {feitisso} o feitiço falhou"

    win.undo_stack.undo()
    assert c_s1_pt.local_value == "Veja {feitisso} o feitisso falhou"
    win.undo_stack.undo()
    assert c_s1_pt.local_value == "O feitisso falhou"

    # Adicionar ao dicionário PWL limpa TODAS as células afetadas em pt-BR
    assert c_s2_pt is not None and any(i.rule_id == "spell:Zorgxp" for i in c_s2_pt.active_spell_issues)
    assert c_s3_pt is not None and any(i.rule_id == "spell:Zorgxp" for i in c_s3_pt.active_spell_issues)
    win.table.setCurrentIndex(win.proxy_model.index(1, 2))
    assert win.add_personal_word_current("Zorgxp") is True
    qtbot.waitUntil(lambda: not win.validation_in_progress, timeout=4000)
    assert c_s2_pt.active_spell_issues == []
    assert c_s3_pt.active_spell_issues == []

    win.save_project(tmp_path / "spell-ui.i18nproj")




