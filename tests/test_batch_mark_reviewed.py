from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QItemSelection, QItemSelectionModel
from pytestqt.qtbot import QtBot

from app.core.project_manager import CellData, CellKind, ManifestInfo, PackageSession, TableRowData
from app.ui.main_window import MainWindow


def _make_session(tmp_path: Path) -> PackageSession:
    rows = [
        TableRowData(
            key_path="MOD.Key1",
            base_text="One",
            cells={
                "pt-BR": CellData(prod_value="Um", local_value="Um", kind=CellKind.TRANSLATED),
                "es": CellData(prod_value="Uno", local_value="Uno", kind=CellKind.TRANSLATED),
            },
        ),
        TableRowData(
            key_path="MOD.Key2",
            base_text="Two",
            cells={
                "pt-BR": CellData(prod_value="Dois", local_value="Dois", kind=CellKind.TRANSLATED),
                "es": CellData(prod_value=None, local_value=None, kind=CellKind.MISSING),
            },
        ),
        TableRowData(
            key_path="MOD.Key3",
            base_text="Three",
            cells={
                "pt-BR": CellData(prod_value="Três", local_value="Três", kind=CellKind.TRANSLATED),
                "es": CellData(prod_value="Tres", local_value="Tres", kind=CellKind.TRANSLATED),
            },
        ),
        TableRowData(
            key_path="MOD.Key4",
            base_text="Four",
            cells={
                "pt-BR": CellData(prod_value="Quatro", local_value="Quatro", kind=CellKind.TRANSLATED),
                "es": CellData(prod_value="Cuatro", local_value="Cuatro", kind=CellKind.TRANSLATED),
            },
        ),
    ]
    manifest = ManifestInfo(
        manifest_path=tmp_path / "module.json",
        package_root=tmp_path,
        manifest_type="module",
        package_id="test-batch",
        default_base_lang="en",
        entries=[],
        warnings=[],
    )
    return PackageSession(
        manifest=manifest,
        base_lang="en",
        base_external_path=None,
        target_langs=["pt-BR", "es"],
        files=[],
        rows=rows,
        warnings=[],
        project_id="test-batch",
    )


def test_batch_mark_reviewed_selection_and_single_undo_redo(qtbot: QtBot, tmp_path: Path) -> None:
    win = MainWindow(app_data_dir=tmp_path)
    qtbot.addWidget(win)
    session = _make_session(tmp_path)
    win.session = session
    win.table_model.set_session(session)

    # Select rectangle covering Key/Base/pt-BR/es across rows 0..1
    sel_model = win.table.selectionModel()
    selection = QItemSelection(win.proxy_model.index(0, 0), win.proxy_model.index(1, 3))
    sel_model.select(selection, QItemSelectionModel.SelectionFlag.ClearAndSelect)

    # Eligible cells in rows 0..1 cols 2..3: (0, pt-BR), (0, es), (1, pt-BR) -> 3 cells
    # (row 1, es is MISSING; cols 0..1 are Key/Base)
    assert win.btn_review_next.text() == "Mark 3 Reviewed + Next (Ctrl+Enter)"

    assert win.mark_current_reviewed() is True
    assert session.rows[0].cells["pt-BR"].review_status == "reviewed"
    assert session.rows[0].cells["es"].review_status == "reviewed"
    assert session.rows[1].cells["pt-BR"].review_status == "reviewed"
    assert session.rows[2].cells["pt-BR"].review_status == "unreviewed"
    assert "Marked 3 cells as reviewed" in win.statusBar().currentMessage()

    # Single undo reverts all 3
    win.undo_stack.undo()
    assert session.rows[0].cells["pt-BR"].review_status == "unreviewed"
    assert session.rows[0].cells["es"].review_status == "unreviewed"
    assert session.rows[1].cells["pt-BR"].review_status == "unreviewed"

    # Single redo re-applies all 3
    win.undo_stack.redo()
    assert session.rows[0].cells["pt-BR"].review_status == "reviewed"
    assert session.rows[0].cells["es"].review_status == "reviewed"
    assert session.rows[1].cells["pt-BR"].review_status == "reviewed"
    win._project_unsaved = False
    win.close()


def test_batch_review_and_advance_jumps_after_last_selected_cell(qtbot: QtBot, tmp_path: Path) -> None:
    win = MainWindow(app_data_dir=tmp_path)
    qtbot.addWidget(win)
    session = _make_session(tmp_path)
    win.session = session
    win.table_model.set_session(session)

    # Select rows 0..1 in pt-BR (col 2)
    sel_model = win.table.selectionModel()
    selection = QItemSelection(win.proxy_model.index(0, 2), win.proxy_model.index(1, 2))
    sel_model.select(selection, QItemSelectionModel.SelectionFlag.ClearAndSelect)
    assert win.btn_review_next.text() == "Mark 2 Reviewed + Next (Ctrl+Enter)"

    win.review_and_advance()
    assert session.rows[0].cells["pt-BR"].review_status == "reviewed"
    assert session.rows[1].cells["pt-BR"].review_status == "reviewed"
    # Should advance to row 2, col 2 (MOD.Key3 in pt-BR)
    assert win.table.currentIndex().row() == 2
    assert win.table.currentIndex().column() == 2
    win._project_unsaved = False
    win.close()
