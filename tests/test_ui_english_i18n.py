from __future__ import annotations

import ast
from pathlib import Path
import re

from PySide6.QtCore import Qt
from pytestqt.qtbot import QtBot

from app.core.project_manager import CellData, CellKind
from app.ui.delegates import _resolve_cell_style
from app.ui.main_window import MainWindow

_PORTUGUESE_CHARS_RE = re.compile(r"[áàâãéêíóôõúçÁÀÂÃÉÊÍÓÔÕÚÇ]")
_PORTUGUESE_UI_WORDS_RE = re.compile(
    r"\b(?:abrir|salvar|editar|remover|reverter|revisar|desfazer|refazer|enviar|restaurar|"
    r"arquivo|arquivos|idioma|idiomas|chave|chaves|estado|erro|erros|aviso|avisos|"
    r"conflito|conflitos|ignorar|reativar|substituir|corrigir|adicionar|inserir|apenas|"
    r"fechar|sincronizar|selecione|nenhum|nenhuma|falha|publicar|regras|referencia|"
    r"voltar|cancelar|lote|lotes|origem|antes|agora|ausente|vazia|ortografia|linha)\b",
    re.IGNORECASE,
)


def _docstring_nodes(tree: ast.AST) -> set[int]:
    ids: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.body and isinstance(node.body[0], ast.Expr) and isinstance(node.body[0].value, ast.Constant):
                ids.add(id(node.body[0].value))
    return ids


def test_no_portuguese_user_facing_strings_remain_in_app() -> None:
    app_root = Path(__file__).resolve().parents[1] / "app"
    offenders: list[str] = []

    for py_file in sorted(app_root.rglob("*.py")):
        tree = ast.parse(py_file.read_text(encoding="utf-8"))
        doc_ids = _docstring_nodes(tree)
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in doc_ids:
                val = node.value
                if _PORTUGUESE_CHARS_RE.search(val) or _PORTUGUESE_UI_WORDS_RE.search(val):
                    offenders.append(f"{py_file.name}:{node.lineno}: {val!r}")

    assert offenders == []


def test_ui_displays_international_english_labels_and_badges(qtbot: QtBot, tmp_path: Path) -> None:
    win = MainWindow(app_data_dir=tmp_path / "appdata")
    qtbot.addWidget(win)

    filter_texts = [win.status_filter_combo.itemText(i) for i in range(win.status_filter_combo.count())]
    assert filter_texts == [
        "All",
        "Pending Only",
        "Edited Only",
        "All Alerts",
        "Glossary Mismatches",
    ]
    assert win.btn_publish.text() == "Send to Production"
    assert win.btn_restore_backup.text() == "Restore Backup"
    assert win.btn_glossary.text() == "Glossary..."
    assert win.btn_custom_enrichers.text() == "Enricher Rules..."

    # Cell style badges in English
    assert _resolve_cell_style(CellData(prod_value="x", local_value="x", kind=CellKind.ORPHAN))[1] == "ORPHAN"
    assert _resolve_cell_style(CellData(prod_value="x", local_value="x", kind=CellKind.ORPHAN, marked_for_deletion=True))[1] == "REMOVE"
    assert _resolve_cell_style(CellData(prod_value="x", local_value="y", kind=CellKind.TRANSLATED))[1] == "EDITED"
    assert _resolve_cell_style(CellData(prod_value="", local_value="", kind=CellKind.EMPTY))[1] == "[empty]"
    assert _resolve_cell_style(CellData(prod_value="1", local_value="1", kind=CellKind.NON_STRING))[1] == "[non-string]"

    # Table header Base suffix in English
    assert "(Base)" in str(win.table_model.headerData(1, Qt.Orientation.Horizontal))

