from pathlib import Path
import shutil

import pytest
from pytestqt.qtbot import QtBot

from app.core.project_manager import CellKind
from app.ui.main_window import MainWindow

_FIXTURE_MANIFEST = Path(__file__).parent / "fixtures" / "sample_package" / "module.json"
_HEARTHBOUND_DIR = Path(r"C:\Users\ajtop\OneDrive\Documents\foundry-vtt-dev\Data\modules\hearthbound")


def test_self_contained_sample_package_fixture_loads_all_cases(qtbot: QtBot) -> None:
    win = MainWindow()
    qtbot.addWidget(win)
    session = win.open_package_manifest(_FIXTURE_MANIFEST)

    assert session.base_lang == "en"
    assert session.target_langs == ["pt-BR", "es", "fr"]
    rows = {r.key_path: r for r in session.rows}

    assert rows["APP.Points.many"].cells["pt-BR"].kind == CellKind.TRANSLATED
    assert rows["INLINE.B"].cells["pt-BR"].kind == CellKind.MISSING
    assert rows["APP.Title"].cells["es"].prod_value == "Segunda"
    assert rows["APP.Title"].cells["fr"].readonly is True
    assert any(d.kind == "duplicate_key" for d in session.file_diagnostics["lang/es-duplicate.json"])
    assert any(d.kind == "leaf_before_branch" for d in session.file_diagnostics["lang/fr-fatal.json"])


@pytest.mark.skipif(not _HEARTHBOUND_DIR.exists(), reason="Local hearthbound module not available")
def test_hearthbound_copy_loads_cleanly_in_main_window(qtbot: QtBot, tmp_path: Path) -> None:
    copy_dir = tmp_path / "hearthbound"
    shutil.copytree(_HEARTHBOUND_DIR / "lang", copy_dir / "lang")
    shutil.copy2(_HEARTHBOUND_DIR / "module.json", copy_dir / "module.json")

    win = MainWindow()
    qtbot.addWidget(win)
    session = win.open_package_manifest(copy_dir / "module.json")

    assert session.base_lang == "en"
    assert session.target_langs == ["pt-BR", "es", "eo"]
    assert len(session.rows) == 1314
    assert not session.file_diagnostics
    assert win.diagnostic_banner.isHidden() is True

