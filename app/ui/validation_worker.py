from __future__ import annotations

from typing import Callable

from PySide6.QtCore import QObject, QRunnable, Signal

from app.core.validator import (
    CustomEnricherRule,
    IgnoredWarning,
    ValidationIssue,
    inspect_base_defects,
    validate_translation,
)

RowValidationSnapshot = tuple[int, str, str | None, dict[str, tuple[str | None, bool]]]


class ValidationSignals(QObject):
    """Qt signal carrier emitted from background validation workers."""

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
        signals: ValidationSignals,
    ) -> None:
        super().__init__()
        self.generation = generation
        self._is_cancelled = is_cancelled
        self.ordered_snapshots = ordered_snapshots
        self.visible_count = visible_count
        self.custom_enrichers = custom_enrichers
        self.ignored_warnings = ignored_warnings
        self.signals = signals

    def run(self) -> None:
        try:
            batch: list[tuple[int, list[ValidationIssue], dict[str, list[ValidationIssue]]]] = []
            for pos, (row_idx, key_path, base_text, cell_map_in) in enumerate(self.ordered_snapshots):
                if self._is_cancelled():
                    return
                base_issues = inspect_base_defects(base_text, custom_enrichers=self.custom_enrichers)
                cell_out: dict[str, list[ValidationIssue]] = {}
                for lang, (val, is_dirty) in cell_map_in.items():
                    cell_out[lang] = validate_translation(
                        key_path,
                        lang,
                        base_text,
                        val,
                        custom_enrichers=self.custom_enrichers,
                        ignored_warnings=self.ignored_warnings,
                        ignore_empty=not is_dirty,
                    )
                batch.append((row_idx, base_issues, cell_out))
                # Flush imediatamente o bloco de linhas visíveis antes das restantes
                at_visible_boundary = self.visible_count > 0 and (pos + 1) == self.visible_count
                if at_visible_boundary or len(batch) >= 200:
                    self.signals.batch_ready.emit(self.generation, batch)
                    batch = []
            if batch and not self._is_cancelled():
                self.signals.batch_ready.emit(self.generation, batch)
        finally:
            self.signals.finished.emit(self.generation)

