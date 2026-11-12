from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QDialog, QMessageBox

from app.core.glossary import GlossaryEntry
from app.core.project_manager import (
    CellKind,
    ConflictResolution,
    PackageSession,
    apply_conflict_resolutions,
    check_external_disk_changes,
    discover_manifest,
    load_package_session,
    load_project_file,
    prepare_disk_sync,
    save_project_file,
    write_recovery_draft,
)
from app.ui.conflict_dialog import ConflictResolutionDialog
from app.ui.main_window import ExpandedEditorDialog, MainWindow


def _make_sample_package(
    tmp_path: Path,
    *,
    en_data: dict[str, Any] | None = None,
    pt_data: dict[str, Any] | None = None,
    include_http: bool = False,
) -> Path:
    pkg = tmp_path / "pkg"
    lang_dir = pkg / "lang"
    lang_dir.mkdir(parents=True, exist_ok=True)
    (lang_dir / "en.json").write_text(
        json.dumps(
            en_data
            if en_data is not None
            else {
                "UI.GREETING": "Hello {name}",
                "UI.TITLE": "<b>Item</b>",
                "UI.COUNT": 42,
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    (lang_dir / "pt-BR.json").write_text(
        json.dumps(
            pt_data
            if pt_data is not None
            else {
                "UI.GREETING": "Olá {name}",
                "UI.TITLE": "<b>Item</b>",
                "UI.COUNT": 42,
                "UI.ORPHAN": "Sobrou",
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    langs: list[dict[str, str]] = [
        {"lang": "en", "name": "English", "path": "lang/en.json"},
        {"lang": "pt-BR", "name": "Português (Brasil)", "path": "lang/pt-BR.json"},
    ]
    if include_http:
        langs.append(
            {
                "lang": "fr",
                "name": "French",
                "path": "https://example.com/lang/fr.json",
            }
        )
    manifest = {
        "id": "base-edit-mod",
        "title": "Base Edit Mod",
        "version": "1.0.0",
        "languages": langs,
    }
    manifest_path = pkg / "module.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest_path


def _row_by_key(session: PackageSession, key: str):
    return next(r for r in session.rows if r.key_path == key)


def test_base_cell_editability_boundaries(tmp_path: Path) -> None:
    manifest_path = _make_sample_package(
        tmp_path,
        pt_data={
            "UI.GREETING": "Olá {name}",
            "UI.COUNT": 42,
            "UI.ORPHAN": "Órfã",
            "UI.TITLE.SUB": "Conflito",
        },
        include_http=True,
    )
    manifest = discover_manifest(manifest_path)

    # Local manifest base: string keys editable; non-string / missing-orphan / conflict readonly.
    session = load_package_session(manifest, base_lang="en")
    row_greet = _row_by_key(session, "UI.GREETING")
    assert row_greet.base_cell is not None
    assert row_greet.base_cell.can_edit() is True
    assert row_greet.base_cell.local_value == "Hello {name}"

    row_count = _row_by_key(session, "UI.COUNT")
    assert row_count.base_cell is not None
    assert row_count.base_cell.kind == CellKind.NON_STRING
    assert row_count.base_cell.can_edit() is False

    row_orphan = _row_by_key(session, "UI.ORPHAN")
    assert row_orphan.base_cell is not None
    assert row_orphan.base_cell.kind == CellKind.MISSING
    assert row_orphan.base_cell.can_edit() is False

    row_conflict = _row_by_key(session, "UI.TITLE.SUB")
    assert row_conflict.base_cell is not None
    assert row_conflict.base_cell.kind == CellKind.STRUCTURAL_CONFLICT
    assert row_conflict.base_cell.can_edit() is False

    # External reference JSON base: base column is completely read-only.
    ext_base = tmp_path / "ext_en.json"
    ext_base.write_text(
        json.dumps({"UI.GREETING": "External hello {name}"}) + "\n",
        encoding="utf-8",
    )
    ext_session = load_package_session(manifest, base_lang="en", base_external_path=ext_base)
    ext_row = _row_by_key(ext_session, "UI.GREETING")
    assert ext_row.base_cell is not None
    assert ext_row.base_cell.can_edit() is False
    assert ext_row.base_cell.readonly is True

    # Remote HTTP declared base: base column is read-only.
    http_session = load_package_session(manifest, base_lang="fr")
    assert all(r.base_cell is None or not r.base_cell.can_edit() for r in http_session.rows)

    # Cross-file structural conflict in base (A.B in file 1, A.B.C in file 2) stays read-only.
    multi_pkg = tmp_path / "multi_pkg"
    (multi_pkg / "lang").mkdir(parents=True)
    (multi_pkg / "lang" / "en-a.json").write_text(json.dumps({"A.B": "Leaf"}) + "\n", encoding="utf-8")
    (multi_pkg / "lang" / "en-b.json").write_text(json.dumps({"A.B.C": "Branch"}) + "\n", encoding="utf-8")
    (multi_pkg / "lang" / "pt-BR.json").write_text(json.dumps({"A.B": "Folha"}) + "\n", encoding="utf-8")
    (multi_pkg / "module.json").write_text(
        json.dumps(
            {
                "id": "multi-conflict",
                "languages": [
                    {"lang": "en", "name": "English A", "path": "lang/en-a.json"},
                    {"lang": "en", "name": "English B", "path": "lang/en-b.json"},
                    {"lang": "pt-BR", "name": "Português", "path": "lang/pt-BR.json"},
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    multi_session = load_package_session(discover_manifest(multi_pkg / "module.json"), base_lang="en")
    for ckey in ("A.B", "A.B.C"):
        crow = _row_by_key(multi_session, ckey)
        assert crow.base_cell is not None
        assert crow.base_cell.kind == CellKind.STRUCTURAL_CONFLICT
        assert crow.base_cell.can_edit() is False


def test_base_edit_persistence_recovery_and_three_way_sync(tmp_path: Path) -> None:
    manifest_path = _make_sample_package(tmp_path)
    manifest = discover_manifest(manifest_path)
    session = load_package_session(manifest, base_lang="en")

    row = _row_by_key(session, "UI.GREETING")
    assert row.base_cell is not None
    pt_cell = row.cells["pt-BR"]
    pt_cell.review_status = "reviewed"

    # Simulate base edit via project save + reload.
    old_base = row.base_text
    row.base_cell.apply_edit("Hello hero {name}!", base_text=None)
    row.set_base_text("Hello hero {name}!")
    pt_cell.review_status = "stale"
    pt_cell.previous_base = old_base

    proj_path = tmp_path / "project.i18nproj"
    save_project_file(session, proj_path)

    loaded = load_project_file(proj_path)
    loaded_row = _row_by_key(loaded.session, "UI.GREETING")
    assert loaded_row.base_text == "Hello hero {name}!"
    assert loaded_row.base_cell is not None
    assert loaded_row.base_cell.is_dirty is True
    assert loaded_row.base_cell.local_value == "Hello hero {name}!"
    assert loaded_row.base_cell.prod_value == "Hello {name}"
    assert loaded_row.cells["pt-BR"].review_status == "stale"
    assert loaded_row.cells["pt-BR"].previous_base == "Hello {name}"

    # Crash recovery preserves base draft too.
    app_data = tmp_path / "appdata"
    loaded_row.base_cell.apply_edit("Crash base {name}", base_text=None)
    loaded_row.set_base_text("Crash base {name}")
    write_recovery_draft(loaded.session, app_data_dir=app_data)

    recovered = load_project_file(proj_path, apply_recovery_dir=app_data)
    rec_row = _row_by_key(recovered.session, "UI.GREETING")
    assert rec_row.base_text == "Crash base {name}"
    assert rec_row.base_cell is not None and rec_row.base_cell.is_dirty is True

    # Modify en.json on disk for BOTH a clean reviewed row and the dirty base row -> sync + 3-way conflict!
    title_row = _row_by_key(recovered.session, "UI.TITLE")
    title_row.cells["pt-BR"].review_status = "reviewed"

    en_path = tmp_path / "pkg" / "lang" / "en.json"
    en_path.write_text(
        json.dumps(
            {
                "UI.GREETING": "Disk base {name}",
                "UI.TITLE": "<b>Magic Item</b>",
                "UI.COUNT": 42,
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    preview = prepare_disk_sync(recovered.session)
    conflicts = preview.report.conflicts
    assert any(c.key_path == "UI.GREETING" and c.lang == "en" for c in conflicts)

    base_conflict = next(c for c in conflicts if c.key_path == "UI.GREETING" and c.lang == "en")
    assert base_conflict.snapshot_value == "Hello {name}"
    assert base_conflict.disk_value == "Disk base {name}"
    assert base_conflict.local_value == "Crash base {name}"

    # Clean UI.TITLE on disk should update base_text and mark pt-BR stale cleanly.
    title_fresh = _row_by_key(preview.fresh_session, "UI.TITLE")
    assert title_fresh.base_text == "<b>Magic Item</b>"
    assert title_fresh.cells["pt-BR"].review_status == "stale"
    assert title_fresh.cells["pt-BR"].previous_base == "<b>Item</b>"

    # Resolve base conflict with manual value -> keeps dirty diff against disk and syncs cleanly.
    apply_conflict_resolutions(
        preview.fresh_session,
        [ConflictResolution(key_path="UI.GREETING", lang="en", choice="manual", manual_value="Merged {name}")],
    )
    greet_fresh = _row_by_key(preview.fresh_session, "UI.GREETING")
    assert greet_fresh.base_text == "Merged {name}"
    assert greet_fresh.base_cell is not None
    assert greet_fresh.base_cell.local_value == "Merged {name}"
    assert greet_fresh.base_cell.prod_value == "Disk base {name}"
    assert greet_fresh.base_cell.is_dirty is True

    # If a locally edited base key is deleted on disk, keep_local preserves local draft over missing disk.
    en_path.write_text(
        json.dumps({"UI.TITLE": "<b>Magic Item</b>", "UI.COUNT": 42}, indent=2) + "\n",
        encoding="utf-8",
    )
    del_preview = prepare_disk_sync(preview.fresh_session)
    del_conflict = next(c for c in del_preview.report.conflicts if c.key_path == "UI.GREETING" and c.lang == "en")
    assert del_conflict.disk_value is None
    assert del_conflict.local_value == "Merged {name}"
    greet_del = _row_by_key(del_preview.fresh_session, "UI.GREETING")
    assert greet_del.base_text == "Merged {name}"
    assert greet_del.base_cell is not None
    assert greet_del.base_cell.prod_value is None
    assert greet_del.base_cell.is_dirty is True


def test_ui_base_editing_undo_revert_revalidation_and_stale(
    qtbot: Any,
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    manifest_path = _make_sample_package(tmp_path)
    monkeypatch.setattr(
        QMessageBox,
        "question",
        lambda *args, **kwargs: QMessageBox.StandardButton.Discard,
    )
    win = MainWindow(app_data_dir=tmp_path / "appdata")
    qtbot.addWidget(win)
    win.show()
    manifest = discover_manifest(manifest_path)
    session = load_package_session(manifest, base_lang="en")
    win.load_session(session)

    # Find UI.GREETING row index
    src_row = next(i for i, r in enumerate(session.rows) if r.key_path == "UI.GREETING")
    base_idx = win.table_model.index(src_row, 1)
    target_idx = win.table_model.index(src_row, 2)

    # Local base cell is editable
    assert bool(win.table_model.flags(base_idx) & Qt.ItemFlag.ItemIsEditable) is True

    # Mark target pt-BR as reviewed first
    win.table.setCurrentIndex(win.proxy_model.mapFromSource(target_idx))
    win.mark_current_reviewed()
    assert session.rows[src_row].cells["pt-BR"].review_status == "reviewed"

    # Edit Base inline via table model setData -> adds placeholder {count} to trigger revalidation & stale!
    win.table.setCurrentIndex(win.proxy_model.mapFromSource(base_idx))
    win._sync_inspector_to_current()
    assert "Base" in win.inspector_state_label.text()
    assert "read-only" not in win.inspector_state_label.text().lower()

    ok = win.table_model.setData(base_idx, "Hello {name} ({count})", Qt.ItemDataRole.EditRole)
    assert ok is True

    row_obj = session.rows[src_row]
    assert row_obj.base_text == "Hello {name} ({count})"
    assert row_obj.base_cell is not None and row_obj.base_cell.is_dirty is True
    assert row_obj.cells["pt-BR"].review_status == "stale"
    assert row_obj.cells["pt-BR"].previous_base == "Hello {name}"
    # Revalidation immediately caught missing {count} placeholder on pt-BR!
    assert any(i.rule_id == "placeholder_mismatch" for i in row_obj.cells["pt-BR"].validation_issues)

    # Inspector on target shows STALE Before / Now comparison
    win.table.setCurrentIndex(win.proxy_model.mapFromSource(target_idx))
    assert win.inspector_stale_label.isVisible()
    assert "Before: Hello {name}" in win.inspector_stale_label.text()
    assert "Now: Hello {name} ({count})" in win.inspector_stale_label.text()

    # "Edited only" filter includes dirty base row
    idx_edited = win.status_filter_combo.findData("edited")
    win.status_filter_combo.setCurrentIndex(idx_edited)
    visible_keys = {
        win.table_model.get_row(win.proxy_model.mapToSource(win.proxy_model.index(r, 0)).row()).key_path
        for r in range(win.proxy_model.rowCount())
    }
    assert "UI.GREETING" in visible_keys
    win.status_filter_combo.setCurrentIndex(0)

    # Undo restores base text AND target reviewed state + clears placeholder alert!
    win.undo_stack.undo()
    assert row_obj.base_text == "Hello {name}"
    assert row_obj.base_cell.is_dirty is False
    assert row_obj.cells["pt-BR"].review_status == "reviewed"
    assert not any(i.rule_id == "placeholder_mismatch" for i in row_obj.cells["pt-BR"].validation_issues)

    # Redo reapplies edit + stale + alert
    win.undo_stack.redo()
    assert row_obj.base_text == "Hello {name} ({count})"
    assert row_obj.cells["pt-BR"].review_status == "stale"

    # Expanded Editor from Base column edits base text cleanly
    monkeypatch.setattr(ExpandedEditorDialog, "exec", lambda self: QDialog.DialogCode.Accepted)
    monkeypatch.setattr(ExpandedEditorDialog, "edited_text", lambda self: "Hello {name} ({count})!")
    win.table.setCurrentIndex(win.proxy_model.mapFromSource(base_idx))
    win.open_expanded_editor()
    assert row_obj.base_text == "Hello {name} ({count})!"
    # Original previous_base should be preserved across consecutive base edits!
    assert row_obj.cells["pt-BR"].previous_base == "Hello {name}"

    # Revert to production on base column restores prod_value and clean state
    win.revert_current_cell()
    assert row_obj.base_text == "Hello {name}"
    assert row_obj.base_cell.is_dirty is False
    assert row_obj.cells["pt-BR"].review_status == "reviewed"


def test_ui_base_sync_conflict_dialog_http_external_and_revalidation(
    qtbot: Any,
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    manifest_path = _make_sample_package(tmp_path, include_http=True)
    monkeypatch.setattr(
        QMessageBox,
        "question",
        lambda *args, **kwargs: QMessageBox.StandardButton.Discard,
    )
    monkeypatch.setattr(QMessageBox, "information", lambda *args, **kwargs: QMessageBox.StandardButton.Ok)

    win = MainWindow(app_data_dir=tmp_path / "appdata")
    qtbot.addWidget(win)
    win.show()

    manifest = discover_manifest(manifest_path)

    # 1. External reference JSON & Remote HTTP Inspector labels + read-only flags
    ext_base = tmp_path / "ext_en.json"
    ext_base.write_text(json.dumps({"UI.GREETING": "External hello {name}"}) + "\n", encoding="utf-8")
    win.load_session(load_package_session(manifest, base_lang="en", base_external_path=ext_base))
    ext_src_row = next(i for i, r in enumerate(win.session.rows) if r.key_path == "UI.GREETING")
    win.table.setCurrentIndex(win.proxy_model.mapFromSource(win.table_model.index(ext_src_row, 1)))
    assert not bool(win.table_model.flags(win.table_model.index(ext_src_row, 1)) & Qt.ItemFlag.ItemIsEditable)
    assert "External reference (Read-only)" in win.inspector_state_label.text()

    win.load_session(load_package_session(manifest, base_lang="fr"))
    win.table.setCurrentIndex(win.proxy_model.mapFromSource(win.table_model.index(0, 1)))
    assert "Remote HTTP reference (Read-only)" in win.inspector_state_label.text()

    # 2. Local editable base: glossary, HTML, base defect & search revalidation + Shift+F2
    session = load_package_session(manifest, base_lang="en")
    session.project_glossary = [
        GlossaryEntry(term="Sword", translations={"pt-BR": "Espada"}, do_not_translate=False)
    ]
    win.load_session(session)

    title_row = next(i for i, r in enumerate(session.rows) if r.key_path == "UI.TITLE")
    base_idx = win.table_model.index(title_row, 1)
    assert win.table_model.setData(
        base_idx,
        "@UUID[Item.1]{name} Epic Sword {name} https://example.com",
        Qt.ItemDataRole.EditRole,
    )
    row_obj = session.rows[title_row]
    # Base defect (enricher/placeholder label collision), glossary mismatch, HTML/URL mismatch all trigger immediately
    assert any(i.rule_id == "base_label_placeholder_collision" for i in row_obj.base_issues)
    assert any(i.rule_id == "glossary:Sword" for i in row_obj.cells["pt-BR"].glossary_issues)
    assert any(i.rule_id == "url_mismatch" for i in row_obj.cells["pt-BR"].validation_issues)
    assert any(i.rule_id == "html_mismatch" for i in row_obj.cells["pt-BR"].validation_issues)

    # Updated base text is searchable
    win.search_input.setText("Epic Sword")
    win._apply_debounced_search()
    assert win.proxy_model.rowCount() == 1
    win.search_input.setText("")
    win._apply_debounced_search()

    # Shift+F2 opens ExpandedEditorDialog in editable_base mode cleanly
    opened_editable_flag: list[bool] = []
    orig_exec = ExpandedEditorDialog.exec

    def _capture_exec(dlg: ExpandedEditorDialog) -> int:
        opened_editable_flag.append(dlg._editable_base)
        dlg._refresh_missing_strip()
        assert "Base notes:" in dlg.live_alert_label.text()
        dlg.target_edit.setPlainText("Hero Sword")
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(ExpandedEditorDialog, "exec", _capture_exec)
    win.table.setCurrentIndex(win.proxy_model.mapFromSource(base_idx))
    QTest.keyClick(win.table, Qt.Key.Key_F2, Qt.KeyboardModifier.ShiftModifier)
    assert opened_editable_flag == [True]
    assert row_obj.base_text == "Hero Sword"
    monkeypatch.setattr(ExpandedEditorDialog, "exec", orig_exec)

    # 3. External disk change detection + MainWindow.sync_with_disk + ConflictResolutionDialog UI resolution
    en_path = tmp_path / "pkg" / "lang" / "en.json"
    en_path.write_text(
        json.dumps(
            {
                "UI.GREETING": "Hello {name}",
                "UI.TITLE": "<b>Disk Sword</b>",
                "UI.COUNT": 42,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    assert "lang/en.json" in check_external_disk_changes(win.session)

    resolved_accept_disk: list[tuple[str, str]] = []

    def _pick_disk(dlg: ConflictResolutionDialog) -> int:
        for w in dlg._row_widgets:
            resolved_accept_disk.append((w.conflict.key_path, w.conflict.lang))
            w.set_choice("accept_disk")
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(ConflictResolutionDialog, "exec", _pick_disk)
    win.sync_with_disk()
    assert ("UI.TITLE", "en") in resolved_accept_disk
    synced_title = _row_by_key(win.session, "UI.TITLE")
    assert synced_title.base_text == "<b>Disk Sword</b>"
    assert synced_title.base_cell is not None and synced_title.base_cell.is_dirty is False

