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
    assert "4 chaves" in win.statusBar().currentMessage()


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
    assert "One" in win.inspector_stale_label.text()

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


