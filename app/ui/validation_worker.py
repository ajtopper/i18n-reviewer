from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from PySide6.QtCore import QObject, QRunnable, Signal

from app.core.glossary import GlossaryEntry, lint_translation_glossary
from app.core.spell_service import SpellService
from app.core.validator import (
    CustomEnricherRule,
    IgnoredWarning,
    ValidationIssue,
    inspect_base_defects,
    validate_translation,
)

@dataclass(frozen=True)
class RowValidationSnapshot:
    """Immutable snapshot of one row passed to ValidationRunnable."""

    row_index: int
    key_path: str
    base_text: str | None
    base_spell_text: str | None
    cell_states: dict[str, tuple[str | None, bool]]


@dataclass(frozen=True)
class RowValidationResult:
    """Validated diagnostics for one TableRowData row."""

    row_index: int
    base_issues: list[ValidationIssue]
    base_spell_issues: list[ValidationIssue]
    cell_validation_issues: dict[str, list[ValidationIssue]]
    cell_glossary_issues: dict[str, list[ValidationIssue]]
    cell_spell_issues: dict[str, list[ValidationIssue]]


class ValidationSignals(QObject):
    """Qt signal carrier emitted from background validation, glossary, and spellcheck workers."""

    batch_ready = Signal(int, list)
    finished = Signal(int)


class ValidationRunnable(QRunnable):
    """Background worker validating visible rows strictly before remaining rows."""

    def __init__(
        self,
        generation: int,
        is_cancelled: Callable[[], bool],
        ordered_snapshots: list[RowValidationSnapshot],
        visible_count: int,
        custom_enrichers: list[CustomEnricherRule],
        ignored_warnings: list[IgnoredWarning],
        glossary_entries: list[GlossaryEntry],
        spell_service: SpellService | None,
        signals: ValidationSignals,
        base_lang: str = "",
    ) -> None:
        super().__init__()
        self.generation = generation
        self._is_cancelled = is_cancelled
        self.ordered_snapshots = ordered_snapshots
        self.visible_count = visible_count
        self.custom_enrichers = custom_enrichers
        self.ignored_warnings = ignored_warnings
        self.glossary_entries = glossary_entries
        self.spell_service = spell_service
        self.signals = signals
        self.base_lang = base_lang

    def run(self) -> None:
        try:
            batch: list[RowValidationResult] = []
            for pos, snap in enumerate(self.ordered_snapshots):
                if self._is_cancelled():
                    return
                row_idx = snap.row_index
                key_path = snap.key_path
                base_text = snap.base_text
                base_spell_text = snap.base_spell_text
                cell_map_in = snap.cell_states
                base_issues = inspect_base_defects(base_text, custom_enrichers=self.custom_enrichers)
                base_spell_issues = (
                    self.spell_service.lint_cell_spelling(
                        key_path,
                        self.base_lang,
                        None,
                        base_spell_text,
                        glossary_entries=self.glossary_entries,
                        custom_enrichers=self.custom_enrichers,
                        ignored_warnings=self.ignored_warnings,
                    )
                    if (self.spell_service is not None and self.base_lang and base_spell_text)
                    else []
                )
                cell_val_out: dict[str, list[ValidationIssue]] = {}
                cell_gloss_out: dict[str, list[ValidationIssue]] = {}
                cell_spell_out: dict[str, list[ValidationIssue]] = {}
                for lang, (val, is_dirty) in cell_map_in.items():
                    cell_val_out[lang] = validate_translation(
                        key_path,
                        lang,
                        base_text,
                        val,
                        custom_enrichers=self.custom_enrichers,
                        ignored_warnings=self.ignored_warnings,
                        ignore_empty=not is_dirty,
                    )
                    cell_gloss_out[lang] = lint_translation_glossary(
                        key_path,
                        lang,
                        base_text,
                        val,
                        self.glossary_entries,
                        custom_enrichers=self.custom_enrichers,
                        ignored_warnings=self.ignored_warnings,
                    )
                    cell_spell_out[lang] = (
                        self.spell_service.lint_cell_spelling(
                            key_path,
                            lang,
                            base_text,
                            val,
                            glossary_entries=self.glossary_entries,
                            custom_enrichers=self.custom_enrichers,
                            ignored_warnings=self.ignored_warnings,
                        )
                        if self.spell_service is not None
                        else []
                    )
                batch.append(
                    RowValidationResult(
                        row_index=row_idx,
                        base_issues=base_issues,
                        base_spell_issues=base_spell_issues,
                        cell_validation_issues=cell_val_out,
                        cell_glossary_issues=cell_gloss_out,
                        cell_spell_issues=cell_spell_out,
                    )
                )
                at_visible_boundary = self.visible_count > 0 and (pos + 1) == self.visible_count
                if at_visible_boundary or len(batch) >= 200:
                    self.signals.batch_ready.emit(self.generation, batch)
                    batch = []
            if batch and not self._is_cancelled():
                self.signals.batch_ready.emit(self.generation, batch)
        finally:
            self.signals.finished.emit(self.generation)
