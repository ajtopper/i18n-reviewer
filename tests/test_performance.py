from __future__ import annotations

from pathlib import Path
import time

from PySide6.QtWidgets import QApplication
from pytestqt.qtbot import QtBot

from app.core.project_manager import (
    CellData,
    CellKind,
    ManifestInfo,
    PackageSession,
    TableRowData,
)
from app.ui.main_window import MainWindow


def _build_large_session(root: Path, count: int = 3000) -> PackageSession:
    rows: list[TableRowData] = []
    for i in range(count):
        if i % 2 == 0:
            base_txt = (
                f"Item {i}: Long narrative RPG text with {{name}} and "
                f"@UUID[Compendium.test.item.{i}]{{Reference}} that wraps across multiple lines."
            )
            pt_txt = f"Item {i}: Texto narrativo longo com {{name}} que quebra em várias linhas na coluna."
        else:
            base_txt = f"Short {i}"
            pt_txt = f"Curto {i}"
        base = CellData(prod_value=base_txt, local_value=base_txt, kind=CellKind.TRANSLATED, is_base_cell=True)
        pt = CellData(prod_value=pt_txt, local_value=pt_txt, kind=CellKind.TRANSLATED)
        rows.append(
            TableRowData(
                key_path=f"MOD.Section.Key{i}",
                base_text=base_txt,
                base_cell=base,
                cells={"pt-BR": pt},
            )
        )
    return PackageSession(
        project_id="perf-test",
        manifest=ManifestInfo(root / "module.json", root, "module", "perf-mod", "en", [], []),
        base_lang="en",
        base_external_path=None,
        target_langs=["pt-BR"],
        files=[],
        rows=rows,
        warnings=[],
    )


def test_large_session_resize_and_viewport_row_sizing(qtbot: QtBot, tmp_path: Path) -> None:
    win = MainWindow(app_data_dir=tmp_path / "appdata")
    qtbot.addWidget(win)
    session = _build_large_session(tmp_path / "pkg", count=3000)

    t_load0 = time.perf_counter()
    win.load_session(session)
    win.show()
    qtbot.waitExposed(win)
    load_elapsed = time.perf_counter() - t_load0
    assert load_elapsed < 2.5

    # Wait for initial background validation so resize timing measures UI responsiveness cleanly
    qtbot.waitUntil(lambda: not win.validation_in_progress, timeout=10000)

    min_h = win.cell_delegate.min_row_height()
    max_h = win.cell_delegate.max_row_height()
    # Visible multiline/wrapped row 0 must expand beyond min_row_height and respect max_row_height (+gridline)
    assert min_h < win.table.rowHeight(0) <= max_h + 2
    # Visible short single-line row 1 stays near min_row_height (+1px gridline)
    assert min_h <= win.table.rowHeight(1) <= min_h + 2

    # Consecutive window resizes must remain fast (no full-model ResizeToContents stall)
    t_res0 = time.perf_counter()
    for w in range(1360, 1460, 10):
        win.resize(w, 800 + (w - 1360))
        QApplication.processEvents()
    resize_elapsed = time.perf_counter() - t_res0
    assert resize_elapsed < 1.5

    # Wait for debounced visible row resize after drag settles
    qtbot.wait(100)
    assert min_h < win.table.rowHeight(0) <= max_h + 2

    # Scrolling down sizes newly revealed multiline rows
    win.table.scrollTo(win.proxy_model.index(1500, 0))
    qtbot.waitUntil(lambda: win.table.rowHeight(1500) > min_h, timeout=2000)
    assert win.table.rowHeight(1500) <= max_h + 2

    # Compact density updates minimum bounds and shrinks short visible rows
    win.table.scrollTo(win.proxy_model.index(0, 0))
    qtbot.wait(50)
    win.btn_compact_density.setChecked(True)
    compact_min = win.cell_delegate.min_row_height()
    assert win.table.verticalHeader().minimumSectionSize() == compact_min
    assert compact_min <= win.table.rowHeight(1) <= compact_min + 2
    win.btn_compact_density.setChecked(False)

    # Editing a single short row to multiline expands that row's height
    assert min_h <= win.table.rowHeight(1) <= min_h + 2
    win.table_model.setData(win.table_model.index(1, 2), "Line 1\nLine 2\nLine 3\nLine 4")
    assert win.table.rowHeight(1) > min_h + 2

    win._project_unsaved = False
    win.close()


def test_delegate_and_model_caching_preserves_bounds_and_avoids_cache_bloat(
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QColor, QFont
    from PySide6.QtWidgets import QStyleOptionViewItem

    win = MainWindow(app_data_dir=tmp_path / "appdata")
    qtbot.addWidget(win)
    session = _build_large_session(tmp_path / "pkg", count=50)
    session.rows[0].cells["pt-BR"].local_value = "Linha 1\nLinha 2\nLinha 3\nLinha 4\nLinha 5\nLinha 6"
    session.rows[1].cells["pt-BR"].local_value = None
    session.rows[1].cells["pt-BR"].kind = CellKind.MISSING
    win.load_session(session)

    delegate = win.cell_delegate
    opt = QStyleOptionViewItem()
    opt.features |= QStyleOptionViewItem.ViewItemFeature.WrapText
    idx_long = win.proxy_model.index(0, 2)
    initial_cache_len = len(delegate._height_cache)
    for w in range(180, 320, 5):
        opt.rect.setWidth(w)
        sz = delegate.sizeHint(opt, idx_long)
        assert delegate.min_row_height() <= sz.height() <= delegate.max_row_height()

    # Cache is keyed by (row, col), so varying column width does not accumulate stale width entries
    assert len(delegate._height_cache) <= initial_cache_len + 1

    key_font = win.table_model.data(win.table_model.index(0, 0), Qt.ItemDataRole.FontRole)
    assert isinstance(key_font, QFont)
    assert key_font is win.table_model.data(win.table_model.index(1, 0), Qt.ItemDataRole.FontRole)

    missing_fg = win.table_model.data(win.table_model.index(1, 2), Qt.ItemDataRole.ForegroundRole)
    assert isinstance(missing_fg, QColor)
    assert missing_fg is win.table_model.data(win.table_model.index(1, 2), Qt.ItemDataRole.ForegroundRole)

    win._project_unsaved = False
    win.close()


def test_inline_typing_debounce_glossary_cache_and_recovery_flush(
    qtbot: QtBot,
    tmp_path: Path,
    monkeypatch,
) -> None:
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QPlainTextEdit

    from app.core.glossary import GlossaryEntry
    from app.core.project_storage import has_recovery_draft
    import app.ui.main_window as mw_mod

    app_data = tmp_path / "appdata"
    win = MainWindow(app_data_dir=app_data)
    qtbot.addWidget(win)
    session = _build_large_session(tmp_path / "pkg", count=30)
    win.load_session(session)
    win.show()
    qtbot.waitExposed(win)
    qtbot.waitUntil(lambda: not win.validation_in_progress, timeout=5000)

    # 1. Glossary cache hits without recomputation and invalidates on update
    g1 = win.merged_glossary()
    g2 = win.merged_glossary()
    assert g1 is g2
    session.project_glossary = [
        GlossaryEntry(term="Sword", translations={"pt-BR": ["Espada"]})
    ]
    g3 = win.merged_glossary()
    assert g3 is not g1 and any(e.term == "Sword" for e in g3)

    # 2. Inline typing is debounced (~120 ms) and avoids rebuilding identical inspector buttons
    idx0 = win.proxy_model.index(0, 2)
    win.table.setCurrentIndex(idx0)
    win.table.edit(idx0)
    editor = win.table.viewport().findChild(QPlainTextEdit)
    assert editor is not None

    eval_calls = 0
    orig_eval = win._on_inline_text_changed

    def tracked_eval(cell, text):
        nonlocal eval_calls
        eval_calls += 1
        orig_eval(cell, text)

    monkeypatch.setattr(win, "_on_inline_text_changed", tracked_eval)

    clear_calls = 0
    orig_clear = win._clear_inspector_dynamic_actions

    def tracked_clear():
        nonlocal clear_calls
        clear_calls += 1
        orig_clear()

    monkeypatch.setattr(win, "_clear_inspector_dynamic_actions", tracked_clear)

    for text in ("T", "Te", "Tex", "Tex ", "Text", "Texto sem token"):
        editor.setPlainText(text)
    assert eval_calls == 0

    qtbot.waitUntil(lambda: eval_calls == 1, timeout=1500)
    assert "Insert: {name}" in [
        win.inspector_dynamic_layout.itemAt(i).widget().text()
        for i in range(win.inspector_dynamic_layout.count())
        if win.inspector_dynamic_layout.itemAt(i).widget() is not None
    ]
    clears_after_first = clear_calls

    # Further typing that preserves identical missing tokens / alerts skips button recreation
    editor.setPlainText("Texto sem token ainda")
    qtbot.waitUntil(lambda: eval_calls == 2, timeout=1500)
    assert clear_calls == clears_after_first
    win.commit_active_inline_editor()

    # 3. Consecutive cell edits debounce write_recovery_draft, and flush persists immediately
    draft_writes = 0
    real_write = mw_mod.write_recovery_draft

    def tracked_write(sess, app_data_dir=None):
        nonlocal draft_writes
        draft_writes += 1
        return real_write(sess, app_data_dir=app_data_dir)

    monkeypatch.setattr(mw_mod, "write_recovery_draft", tracked_write)

    for r in range(1, 6):
        assert win.proxy_model.setData(
            win.proxy_model.index(r, 2), f"Editado {r}", Qt.ItemDataRole.EditRole
        ) is True
    assert draft_writes == 0
    assert "30 keys · 0 reviewed · 6 edited · 0 missing · 0 orphans" in win.statusBar().currentMessage()

    # Explicit flush / save path writes immediately without waiting for 500 ms timer
    win._flush_recovery_draft()
    assert draft_writes == 1
    assert has_recovery_draft(session.project_id, app_data_dir=app_data) is True

    proj_path = tmp_path / "perf.i18nproj"
    assert win.save_project(proj_path) is True
    assert has_recovery_draft(session.project_id, app_data_dir=app_data) is False

    win._project_unsaved = False
    win.close()


def test_compiled_glossary_validation_equivalence_and_throughput(
    tmp_path: Path,
) -> None:
    from app.core.glossary import (
        GlossaryEntry,
        compile_glossary,
        detect_base_glossary_matches,
        lint_translation_glossary,
        mask_glossary_phrases,
        mask_technical_spans,
    )
    from app.core.spell_service import SpellService
    from app.core.validator import (
        CustomEnricherRule,
        IgnoredWarning,
        compute_value_hash,
        inspect_base_defects,
        term_boundary_pattern,
        validate_translation,
    )
    from app.ui.validation_worker import (
        RowValidationResult,
        RowValidationSnapshot,
        ValidationRunnable,
        ValidationSignals,
    )

    # 1. term_boundary_pattern is cached
    assert term_boundary_pattern("Fireball", case_sensitive=True) is term_boundary_pattern(
        "Fireball", case_sensitive=True
    )
    assert term_boundary_pattern("Fireball", case_sensitive=False) is not term_boundary_pattern(
        "Fireball", case_sensitive=True
    )

    entries = [
        GlossaryEntry(
            term="Spell Slot",
            source_variants=["spell slots"],
            case_sensitive=False,
            translations={"pt-BR": ["Espaço de Magia", "Espaços de Magia"]},
        ),
        GlossaryEntry(
            term="Long Rest",
            case_sensitive=False,
            translations={"pt-BR": ["Descanso Longo"]},
        ),
        GlossaryEntry(
            term="HP",
            case_sensitive=True,
            do_not_translate=True,
        ),
        GlossaryEntry(
            term="Gold",
            case_sensitive=False,
            translations={"pt-BR": ["Ouro"]},
        ),
    ] + [
        GlossaryEntry(
            term=f"GlossaryTerm{i}",
            source_variants=[f"VariantTerm{i}"],
            translations={"pt-BR": [f"TermoGlossario{i}"]},
        )
        for i in range(150)
    ]
    compiled = compile_glossary(entries)
    enrichers = [CustomEnricherRule(name="CustomTag", pattern=r"%[A-Z]+%")]

    sample_cases = [
        (
            "MOD.Case0",
            "Spend a Spell Slot to regain HP and finish a Long Rest with {name} and %TAG%.",
            "Gaste um Espaço de Magia para recuperar HP após Descanso Longo com {name} e %TAG%.",
            False,
        ),
        (
            "MOD.Case1",
            "Take gold during long rest with hp lower than @UUID[Compendium.a.b]{Long Rest}!",
            "Pegue prata durante pausa longa com {missing} e PalavraErradaXYZ",
            True,
        ),
        (
            "MOD.Case2",
            "Empty base ignored or dirty",
            "",
            True,
        ),
        (
            "MOD.Case3",
            "Use spell slots for GlossaryTerm7 and Gold",
            "Use Espaços de Magia para Ouro",
            False,
        ),
    ]
    ignored = [
        IgnoredWarning(
            key_path="MOD.Case1",
            lang="pt-BR",
            rule_id="glossary:Long Rest",
            value_hash=compute_value_hash(sample_cases[1][2]),
            reason="Estilo intencional",
        ),
        IgnoredWarning(
            key_path="MOD.Case1",
            lang="pt-BR",
            rule_id="spell:PalavraErradaXYZ",
            value_hash=compute_value_hash(sample_cases[1][2]),
            reason="Termo de lore",
        ),
    ]

    spell_svc = SpellService(app_data_dir=tmp_path / "appdata")
    for key_path, base_txt, pt_txt, _dirty in sample_cases:
        direct_matches = detect_base_glossary_matches(base_txt, entries, custom_enrichers=enrichers)
        comp_matches = detect_base_glossary_matches(
            base_txt, entries, custom_enrichers=enrichers, compiled=compiled
        )
        assert comp_matches == direct_matches

        masked = mask_technical_spans(pt_txt, custom_enrichers=enrichers)
        assert mask_glossary_phrases(masked, "pt-BR", entries) == mask_glossary_phrases(
            masked, "pt-BR", entries, compiled=compiled
        )

    snapshots = [
        RowValidationSnapshot(
            row_index=i,
            key_path=key_path,
            base_text=base_txt,
            base_spell_text=base_txt,
            cell_states={"pt-BR": (pt_txt, is_dirty), "eo": (pt_txt, is_dirty)},
        )
        for i, (key_path, base_txt, pt_txt, is_dirty) in enumerate(sample_cases)
    ]

    emitted: list[RowValidationResult] = []
    signals = ValidationSignals()
    signals.batch_ready.connect(lambda _gen, batch: emitted.extend(batch))
    ValidationRunnable(
        generation=1,
        is_cancelled=lambda: False,
        ordered_snapshots=snapshots,
        visible_count=2,
        custom_enrichers=enrichers,
        ignored_warnings=ignored,
        glossary_entries=entries,
        spell_service=spell_svc,
        signals=signals,
        base_lang="en",
    ).run()

    assert [r.row_index for r in emitted] == [0, 1, 2, 3]
    for r, (key_path, base_txt, pt_txt, is_dirty) in zip(emitted, sample_cases):
        assert r.base_issues == inspect_base_defects(base_txt, custom_enrichers=enrichers)
        assert r.base_spell_issues == spell_svc.lint_cell_spelling(
            key_path,
            "en",
            None,
            base_txt,
            glossary_entries=entries,
            custom_enrichers=enrichers,
            ignored_warnings=ignored,
        )
        for lang in ("pt-BR", "eo"):
            assert r.cell_validation_issues[lang] == validate_translation(
                key_path,
                lang,
                base_txt,
                pt_txt,
                custom_enrichers=enrichers,
                ignored_warnings=ignored,
                ignore_empty=not is_dirty,
            )
            assert r.cell_glossary_issues[lang] == lint_translation_glossary(
                key_path,
                lang,
                base_txt,
                pt_txt,
                entries,
                custom_enrichers=enrichers,
                ignored_warnings=ignored,
            )
            assert r.cell_spell_issues[lang] == spell_svc.lint_cell_spelling(
                key_path,
                lang,
                base_txt,
                pt_txt,
                glossary_entries=entries,
                custom_enrichers=enrichers,
                ignored_warnings=ignored,
            )

    # 2. Large batch throughput with 1,000 rows x 154 glossary entries
    big_snaps = [
        RowValidationSnapshot(
            row_index=i,
            key_path=f"MOD.Bulk.{i}",
            base_text=f"Item {i}: Gain HP and a Spell Slot with {{name}} and @UUID[Compendium.a.b.{i}]{{Ref}}.",
            base_spell_text=f"Item {i}: Gain HP and a Spell Slot with {{name}} and Ref.",
            cell_states={
                "pt-BR": (f"Item {i}: Ganhe HP e Espaço de Magia com {{name}}.", False),
                "eo": (f"Itemo {i} sen vortaro.", False),
            },
        )
        for i in range(1000)
    ]
    t0 = time.perf_counter()
    bulk_out: list[RowValidationResult] = []
    bulk_signals = ValidationSignals()
    bulk_signals.batch_ready.connect(lambda _gen, batch: bulk_out.extend(batch))
    ValidationRunnable(
        generation=2,
        is_cancelled=lambda: False,
        ordered_snapshots=big_snaps,
        visible_count=30,
        custom_enrichers=enrichers,
        ignored_warnings=[],
        glossary_entries=entries,
        spell_service=spell_svc,
        signals=bulk_signals,
        base_lang="en",
    ).run()
    elapsed = time.perf_counter() - t0
    assert len(bulk_out) == 1000
    assert elapsed < 3.0


def test_spell_unavailable_skips_masking_and_offscreen_batch_skips_repaint(
    qtbot: QtBot,
    tmp_path: Path,
    monkeypatch,
) -> None:
    import app.core.spell_service as spell_mod
    from app.ui.validation_worker import RowValidationResult

    svc = spell_mod.SpellService(app_data_dir=tmp_path / "appdata")
    mask_calls = 0
    orig_mask = spell_mod.mask_technical_spans

    def tracked_mask(*a, **kw):
        nonlocal mask_calls
        mask_calls += 1
        return orig_mask(*a, **kw)

    monkeypatch.setattr(spell_mod, "mask_technical_spans", tracked_mask)
    assert svc.lint_cell_spelling("MOD.K", "eo", "Hello {name}", "Saluton {name}") == []
    assert mask_calls == 0

    win = MainWindow(app_data_dir=tmp_path / "appdata2")
    qtbot.addWidget(win)
    session = _build_large_session(tmp_path / "pkg2", count=500)
    win.load_session(session)
    win.show()
    qtbot.waitExposed(win)
    qtbot.waitUntil(lambda: not win.validation_in_progress, timeout=10000)

    vp = win.table.viewport()
    vp_updates = 0
    orig_vp_update = vp.update

    def tracked_update(*a, **kw):
        nonlocal vp_updates
        vp_updates += 1
        return orig_vp_update(*a, **kw)

    monkeypatch.setattr(vp, "update", tracked_update)
    gen = win._validation_gen
    offscreen = [
        RowValidationResult(
            row_index=490,
            base_issues=[],
            base_spell_issues=[],
            cell_validation_issues={},
            cell_glossary_issues={},
            cell_spell_issues={},
        )
    ]
    win._on_validation_batch_ready(gen, offscreen)
    assert vp_updates == 0

    onscreen = [
        RowValidationResult(
            row_index=0,
            base_issues=[],
            base_spell_issues=[],
            cell_validation_issues={},
            cell_glossary_issues={},
            cell_spell_issues={},
        )
    ]
    win._on_validation_batch_ready(gen, onscreen)
    assert vp_updates >= 1

    win._project_unsaved = False
    win.close()
