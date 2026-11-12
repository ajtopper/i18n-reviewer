from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMessageBox

from app import main as app_main
from app.core.backup_manager import (
    commit_publish_result,
    execute_publish_plan,
    list_backup_batches,
    prepare_publish_plan,
    restore_backup,
    rollback_publish_batch,
)
from app.core.glossary import GlossaryEntry
from app.core.project_manager import (
    CellKind,
    TableRowData,
    discover_manifest,
    load_package_session,
)
from app.core.spell_service import SpellDictStatus
from app.ui.main_window import MainWindow


def _make_publish_package(tmp_path: Path) -> Path:
    pkg = tmp_path / "pub_pkg"
    lang_dir = pkg / "lang"
    lang_dir.mkdir(parents=True, exist_ok=True)
    # Deliberately preserve 4-space indent to test surgical span preservation on base publish
    (lang_dir / "en.json").write_text(
        '{\n    "UI.GREETING": "Hello {name}",\n    "UI.SUBTITLE": "Wooden Sword"\n}\n',
        encoding="utf-8",
    )
    (lang_dir / "pt-BR.json").write_text(
        '{\n  "UI.GREETING": "Olá {name}",\n  "UI.SUBTITLE": "Espada de Madeira"\n}\n',
        encoding="utf-8",
    )
    manifest = {
        "id": "base-pub-mod",
        "title": "Base Pub Mod",
        "version": "1.0.0",
        "languages": [
            {"lang": "en", "name": "English", "path": "lang/en.json"},
            {"lang": "pt-BR", "name": "Português (Brasil)", "path": "lang/pt-BR.json"},
        ],
    }
    manifest_path = pkg / "module.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest_path


def _row_by_key(session: Any, key: str) -> TableRowData:
    return next(r for r in session.rows if r.key_path == key)


def test_prepare_and_execute_publish_base_file_backup_rollback_and_external_check(
    tmp_path: Path,
) -> None:
    manifest_path = _make_publish_package(tmp_path)
    app_data = tmp_path / "appdata"
    manifest = discover_manifest(manifest_path)
    session = load_package_session(manifest, base_lang="en")

    row = _row_by_key(session, "UI.GREETING")
    pt_cell = row.cells["pt-BR"]
    pt_cell.review_status = "reviewed"
    row.apply_base_edit("Hello hero {name}!")
    assert pt_cell.review_status == "stale"

    plan = prepare_publish_plan(session, app_data_dir=app_data)
    assert plan.external_changes == []
    base_fp = next((fp for fp in plan.file_plans if fp.lang == "en"), None)
    assert base_fp is not None
    assert base_fp.rel_path == "lang/en.json"
    assert not base_fp.is_blocked
    assert base_fp.edited_keys == {"UI.GREETING": "Hello hero {name}!"}
    assert any("pt-BR" in w for w in base_fp.validation_warnings)

    # Surgical formatting preservation check (4-space indentation stays intact on untouched keys)
    candidate_text = base_fp.candidate_bytes.decode("utf-8")
    assert '    "UI.GREETING": "Hello hero {name}!",' in candidate_text
    assert '    "UI.SUBTITLE": "Wooden Sword"' in candidate_text

    # Pending sync conflict on base key blocks publish cleanly
    session.pending_conflict_keys.add(("UI.GREETING", "en"))
    blocked_plan = prepare_publish_plan(session, app_data_dir=app_data)
    blocked_base_fp = next(fp for fp in blocked_plan.file_plans if fp.lang == "en")
    assert blocked_base_fp.is_blocked
    assert any("Pending sync conflict" in reason for reason in blocked_base_fp.blocking_reasons)
    session.pending_conflict_keys.clear()

    # Partial failure during multi-file publish [base + target] + rollback restores both .bak files
    sub_row = _row_by_key(session, "UI.SUBTITLE")
    sub_row.cells["pt-BR"].apply_edit("Espada Épica", base_text=sub_row.base_text)
    multi_plan = prepare_publish_plan(session, app_data_dir=app_data)
    ordered_plans = sorted(multi_plan.file_plans, key=lambda fp: 0 if fp.lang == "en" else 1)
    assert len(ordered_plans) == 2

    calls = 0

    def _fail_second_replace(src: str | Path, dst: str | Path) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("Simulated write failure on second file")
        Path(src).replace(dst)

    fail_res = execute_publish_plan(
        session,
        ordered_plans,
        app_data_dir=app_data,
        replace_fn=_fail_second_replace,
        sleep_fn=lambda _d: None,
    )
    assert fail_res.failed_file == "lang/pt-BR.json"
    assert fail_res.batch_id is not None
    assert row.base_cell is not None and row.base_cell.is_dirty is True

    reverted = rollback_publish_batch(
        session,
        fail_res.batch_id,
        rel_paths=fail_res.published_files,
        app_data_dir=app_data,
    )
    assert "lang/en.json" in reverted
    assert '"Hello {name}"' in (tmp_path / "pub_pkg" / "lang" / "en.json").read_text(encoding="utf-8")

    # PermissionError retry with exponential backoff succeeds on base file write
    sleep_delays: list[float] = []
    retry_attempts = 0

    def _retry_once_replace(src: str | Path, dst: str | Path) -> None:
        nonlocal retry_attempts
        retry_attempts += 1
        if retry_attempts == 1:
            raise PermissionError("Transient AV lock on en.json")
        Path(src).replace(dst)

    ok_res = execute_publish_plan(
        session,
        [base_fp],
        app_data_dir=app_data,
        replace_fn=_retry_once_replace,
        sleep_fn=sleep_delays.append,
    )
    assert sleep_delays == [0.1]
    assert retry_attempts == 2
    assert ok_res.failed_file is None
    assert ok_res.published_files == ["lang/en.json"]
    assert row.base_cell.is_dirty is False
    assert row.base_cell.prod_value == "Hello hero {name}!"
    assert '"Hello hero {name}!"' in (tmp_path / "pub_pkg" / "lang" / "en.json").read_text(encoding="utf-8")

    # External disk change on published base file triggers external_changes detection
    (tmp_path / "pub_pkg" / "lang" / "en.json").write_text(
        '{\n    "UI.GREETING": "Modified outside {name}"\n}\n',
        encoding="utf-8",
    )
    ext_plan = prepare_publish_plan(session, app_data_dir=app_data)
    assert "lang/en.json" in ext_plan.external_changes

    # Read-only / missing / STRUCTURAL_CONFLICT base cells never schedule writes without errors
    row.base_cell.kind = CellKind.STRUCTURAL_CONFLICT
    row.base_cell.local_value = "Bad"
    commit_publish_result(session, ok_res)


def test_restore_backup_base_file_and_resync_or_discard(tmp_path: Path) -> None:
    manifest_path = _make_publish_package(tmp_path)
    app_data = tmp_path / "appdata"
    manifest = discover_manifest(manifest_path)
    session = load_package_session(manifest, base_lang="en")

    row = _row_by_key(session, "UI.GREETING")
    row.apply_base_edit("Published typo {name}")
    plan = prepare_publish_plan(session, app_data_dir=app_data)
    pub_res = execute_publish_plan(session, plan.file_plans, app_data_dir=app_data)
    assert pub_res.batch_id is not None

    # Make local dirty edits on both keys (UI.GREETING conflicts with restored disk value when discard=False)
    row.apply_base_edit("Local greeting draft {name}")
    sub_row = _row_by_key(session, "UI.SUBTITLE")
    sub_row.apply_base_edit("Unpublished local draft")
    conflict_res = restore_backup(
        session,
        batch_id=pub_res.batch_id,
        rel_paths=["lang/en.json"],
        discard_local_drafts=False,
        app_data_dir=app_data,
    )
    assert conflict_res.sync_preview is not None
    assert any(
        c.lang == "en" and c.key_path == "UI.GREETING"
        for c in conflict_res.sync_preview.report.conflicts
    )
    assert row.base_cell is not None and row.base_cell.is_dirty is True
    assert sub_row.base_cell is not None and sub_row.base_cell.is_dirty is True

    # Now restore with discard=True (cleanly reverts unpublished dirty base draft to production)
    restore_res = restore_backup(
        session,
        batch_id=pub_res.batch_id,
        rel_paths=["lang/en.json"],
        discard_local_drafts=True,
        app_data_dir=app_data,
    )
    assert restore_res.restored_files == ["lang/en.json"]
    assert restore_res.pre_restore_batch_id is not None
    batches = list_backup_batches(session.project_id, app_data_dir=app_data)
    assert any(b.kind == "pre-restore" and b.batch_id == restore_res.pre_restore_batch_id for b in batches)

    en_disk = (tmp_path / "pub_pkg" / "lang" / "en.json").read_text(encoding="utf-8")
    assert '"Hello {name}"' in en_disk
    restored_greet = _row_by_key(session, "UI.GREETING")
    restored_sub = _row_by_key(session, "UI.SUBTITLE")
    assert restored_greet.base_text == "Hello {name}"
    assert restored_sub.base_text == "Wooden Sword"
    assert restored_sub.base_cell is not None and restored_sub.base_cell.is_dirty is False


def test_base_hunspell_batch_context_menu_undo_pwl_and_self_test(
    qtbot: Any,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest_path = _make_publish_package(tmp_path)
    app_data = tmp_path / "appdata"
    monkeypatch.setattr(
        QMessageBox,
        "question",
        lambda *args, **kwargs: QMessageBox.StandardButton.Discard,
    )

    win = MainWindow(app_data_dir=app_data)
    qtbot.addWidget(win)
    win.show()

    manifest = discover_manifest(manifest_path)
    session = load_package_session(manifest, base_lang="en")
    # Include a non-dictionary glossary fantasy term "Mythril" that should be masked from base spellcheck
    session.project_glossary = [
        GlossaryEntry(term="Mythril", translations={"pt-BR": ["Mythril"]}, do_not_translate=True)
    ]
    row_greet = _row_by_key(session, "UI.GREETING")
    row_greet.apply_base_edit("Helo Mythril {name}")
    win.load_session(session)

    qtbot.waitUntil(lambda: not win.validation_in_progress, timeout=5000)

    assert row_greet.base_cell is not None
    assert any(i.rule_id == "spell:Helo" for i in row_greet.base_cell.spell_issues)
    assert not any(i.rule_id == "spell:Mythril" for i in row_greet.base_cell.spell_issues)

    # Inspector displays spell suggestion + Ignore button on Base cell
    src_row = session.rows.index(row_greet)
    base_idx = win.table_model.index(src_row, 1)
    win.table.setCurrentIndex(win.proxy_model.mapFromSource(base_idx))
    assert "Suggestions:" in win.inspector_diag_label.text()

    # Live inline typing re-evaluates Base spellcheck immediately
    win._on_inline_text_changed(row_greet.base_cell, "Wrnog {name}")
    assert any(i.rule_id == "spell:Wrnog" for i in row_greet.base_cell.spell_issues)
    win._on_inline_text_changed(row_greet.base_cell, "Helo Mythril {name}")
    assert any(i.rule_id == "spell:Helo" for i in row_greet.base_cell.spell_issues)
    win._sync_inspector_to_current(include_spell_suggestions=True)

    # Context menu offers Fix '...' -> '...' and Add '...' to dictionary
    menu = win._build_cell_context_menu(row_greet, row_greet.base_cell, 1)
    action_texts = [a.text() for a in menu.actions()]
    assert "Add term to glossary..." not in action_texts
    fix_action = next((a for a in menu.actions() if a.text().startswith("Fix 'Helo' → ")), None)
    assert fix_action is not None, f"Expected spell fix action in {action_texts}"
    assert any(a.text() == "Add 'Helo' to dictionary" for a in menu.actions())

    # Triggering fix modifies Base text via QUndoStack and supports Undo/Redo
    fix_action.trigger()
    assert "Helo" not in (row_greet.base_text or "")
    win.undo_stack.undo()
    assert row_greet.base_text == "Helo Mythril {name}"
    win.undo_stack.redo()
    assert "Helo" not in (row_greet.base_text or "")
    win.undo_stack.undo()

    # Add to personal dictionary clears spell:Helo across session
    assert win.add_personal_word_current("Helo") is True
    qtbot.waitUntil(lambda: not win.validation_in_progress, timeout=5000)
    assert not any(i.rule_id == "spell:Helo" for i in row_greet.base_cell.spell_issues)

    # Missing dictionary indicator reflects on Base header (col 1) and Inspector
    orig_status = win.spell_service.status_for

    def _missing_en_status(lang: str, *, open_dict: bool = True) -> SpellDictStatus:
        if lang == "en":
            return SpellDictStatus(lang="en", enchant_tag="en_US", available=False, message="No en_US dict.")
        return orig_status(lang, open_dict=open_dict)

    monkeypatch.setattr(win.spell_service, "status_for", _missing_en_status)
    win._refresh_spell_header_statuses(session, open_dicts=False)
    header_label = win.table_model.headerData(1, Qt.Orientation.Horizontal, Qt.ItemDataRole.DisplayRole)
    assert "(no spellcheck)" in str(header_label)
    header_tip = win.table_model.headerData(1, Qt.Orientation.Horizontal, Qt.ItemDataRole.ToolTipRole)
    assert "No en_US dict." in str(header_tip)
    win._sync_inspector_to_current()
    assert "[spellcheck] No en_US dict." in win.inspector_diag_label.text()

    # --self-test verifies en_US alongside the 4 target languages and fails if en is unavailable
    monkeypatch.setattr(win.spell_service, "status_for", orig_status)
    assert app_main.run_self_test(app_data_dir=tmp_path / "selftest_en") == 0
    monkeypatch.setattr(
        "app.core.spell_service.SpellService.is_available",
        lambda _self, lang: lang != "en",
    )
    assert app_main.run_self_test(app_data_dir=tmp_path / "selftest_en_fail") != 0
