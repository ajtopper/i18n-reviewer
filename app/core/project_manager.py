from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Literal
import uuid

from app.core.glossary import GlossaryEntry
from app.core.json_handler import (
    DiagnosticIssue,
    LangEntry,
    ParsedLangDocument,
    parse_lang_bytes,
)
from app.core.validator import (
    CustomEnricherRule,
    IgnoredWarning,
    IssueSeverity,
    ValidationIssue,
)

_PLURAL_SUFFIXES = frozenset({"zero", "one", "two", "few", "many", "other"})
_CLDR_CATEGORIES: dict[str, tuple[str, ...]] = {
    "en": ("one", "other"),
    "de": ("one", "other"),
    "eo": ("one", "other"),
    "pt": ("one", "many", "other"),
    "es": ("one", "many", "other"),
    "fr": ("one", "many", "other"),
}
_BCP47_TAG_RE = re.compile(r"^[a-z]{2,3}(?:-[A-Z][a-z]{3})?(?:-(?:[A-Z]{2}|\d{3}))?$")

ManifestWarningKind = Literal[
    "non_canonical_bcp47",
    "case_collision",
    "remote_http",
    "path_escape",
    "missing_file",
    "multi_file_collision",
    "fatal_file",
]
ReviewStatus = Literal["unreviewed", "reviewed", "stale"]


class CellKind(str, Enum):
    """Semantic classification of a target translation cell relative to the base language."""

    TRANSLATED = "translated"
    MISSING = "missing"
    EMPTY = "empty"
    SAME_AS_BASE = "same_as_base"
    ORPHAN = "orphan"
    NON_STRING = "non_string"
    STRUCTURAL_CONFLICT = "structural_conflict"
    NOT_APPLICABLE = "not_applicable"


@dataclass(frozen=True)
class ManifestWarning:
    """Warning raised while inspecting package manifest or language entries."""

    kind: ManifestWarningKind
    lang: str
    message: str
    path: str = ""
    key_path: str = ""


@dataclass(frozen=True)
class ManifestLangEntry:
    """Single entry declared in module.json/system.json languages[]."""

    lang: str
    name: str
    path: str
    editable: bool = True
    is_http: bool = False
    conditional: str | None = None
    resolved_path: Path | None = None


@dataclass(frozen=True)
class ManifestInfo:
    """Discovered package metadata and language files from a Foundry manifest."""

    manifest_path: Path
    package_root: Path
    manifest_type: Literal["module", "system"]
    package_id: str
    default_base_lang: str
    entries: list[ManifestLangEntry]
    warnings: list[ManifestWarning]


@dataclass(frozen=True)
class CellSnapshot:
    """Captured state of a CellData for undo/redo restoration."""

    local_value: str | None
    review_status: ReviewStatus
    previous_base: str | None
    kind: CellKind
    marked_for_deletion: bool


@dataclass
class CellData:
    """State machine and read-model for a single (key_path, target_lang) cell."""

    prod_value: str | None
    local_value: str | None
    kind: CellKind
    source_file: str = ""
    line: int = 0
    raw_type: str = "str"
    readonly: bool = False
    is_plural_suggestion: bool = False
    marked_for_deletion: bool = False
    review_status: ReviewStatus = "unreviewed"
    previous_base: str | None = None
    validation_issues: list[ValidationIssue] = field(default_factory=list, compare=False, repr=False)
    glossary_issues: list[ValidationIssue] = field(default_factory=list, compare=False, repr=False)
    spell_issues: list[ValidationIssue] = field(default_factory=list, compare=False, repr=False)

    @property
    def active_validation_issues(self) -> list[ValidationIssue]:
        return [i for i in self.validation_issues if not i.is_ignored]

    @property
    def active_glossary_issues(self) -> list[ValidationIssue]:
        return [i for i in self.glossary_issues if not i.is_ignored]

    @property
    def active_spell_issues(self) -> list[ValidationIssue]:
        return [i for i in self.spell_issues if not i.is_ignored]

    @property
    def all_validation_issues(self) -> list[ValidationIssue]:
        return [*self.validation_issues, *self.glossary_issues, *self.spell_issues]

    @property
    def validation_severity(self) -> IssueSeverity | None:
        active = [*self.active_validation_issues, *self.active_glossary_issues, *self.active_spell_issues]
        if any(i.severity == "critical" for i in active):
            return "critical"
        if any(i.severity == "warning" for i in active):
            return "warning"
        return None

    @property
    def is_missing(self) -> bool:
        return self.local_value is None

    @property
    def is_dirty(self) -> bool:
        return (self.local_value != self.prod_value) or self.marked_for_deletion

    @property
    def is_pending(self) -> bool:
        if self.kind in (CellKind.NOT_APPLICABLE, CellKind.NON_STRING, CellKind.STRUCTURAL_CONFLICT):
            return False
        if self.marked_for_deletion:
            return False
        return (
            self.is_missing
            or self.kind == CellKind.EMPTY
            or self.review_status in ("unreviewed", "stale")
        )

    def can_edit(self) -> bool:
        """True if the user is allowed to edit this cell's text."""
        return not (
            self.readonly
            or self.marked_for_deletion
            or self.kind in (CellKind.NON_STRING, CellKind.STRUCTURAL_CONFLICT, CellKind.NOT_APPLICABLE)
        )

    def can_mark_reviewed(self) -> bool:
        """True if the cell can be explicitly approved as reviewed."""
        return self.can_edit() and not self.is_missing

    def will_apply_edit(self, new_value: str | None) -> bool:
        """True if applying new_value would actually change this cell."""
        if not self.can_edit():
            return False
        if self.prod_value is None and (new_value is None or new_value == ""):
            return self.local_value is not None
        return new_value != self.local_value

    def snapshot(self) -> CellSnapshot:
        return CellSnapshot(
            local_value=self.local_value,
            review_status=self.review_status,
            previous_base=self.previous_base,
            kind=self.kind,
            marked_for_deletion=self.marked_for_deletion,
        )

    def restore(self, snap: CellSnapshot) -> None:
        self.local_value = snap.local_value
        self.review_status = snap.review_status
        self.previous_base = snap.previous_base
        self.kind = snap.kind
        self.marked_for_deletion = snap.marked_for_deletion

    def _recompute_kind(self, base_text: str | None) -> None:
        if self.kind == CellKind.ORPHAN:
            return
        if self.local_value is None:
            self.kind = CellKind.MISSING
        elif self.local_value == "":
            self.kind = CellKind.EMPTY
        elif base_text is not None and self.local_value == base_text:
            self.kind = CellKind.SAME_AS_BASE
        else:
            self.kind = CellKind.TRANSLATED

    def apply_edit(self, new_value: str | None, base_text: str | None = None) -> bool:
        """Apply an edit to local_value, updating dirty state and downgrading review_status."""
        if not self.will_apply_edit(new_value):
            return False
        target_val: str | None = (
            None if (self.prod_value is None and (new_value is None or new_value == "")) else new_value
        )
        was_orphan = self.kind == CellKind.ORPHAN
        self.local_value = target_val
        if target_val != self.prod_value:
            self.review_status = "unreviewed"
        if not was_orphan:
            self._recompute_kind(base_text)
        return True

    def mark_reviewed(self) -> bool:
        """Explicitly approve the current translation unless missing, readonly, or slated for deletion."""
        if not self.can_mark_reviewed():
            return False
        self.review_status = "reviewed"
        self.previous_base = None
        return True

    def revert_to_production(self, base_text: str | None = None) -> bool:
        """Discard local draft and deletion mark, restoring prod_value."""
        if not self.is_dirty:
            return False
        was_orphan = self.kind == CellKind.ORPHAN
        self.local_value = self.prod_value
        self.marked_for_deletion = False
        self.review_status = "unreviewed"
        if not was_orphan:
            self._recompute_kind(base_text)
        return True

    def set_marked_for_deletion(self, flag: bool) -> bool:
        """Mark or unmark an orphan key for removal in the next production publish."""
        if self.readonly or self.kind != CellKind.ORPHAN:
            return False
        if self.marked_for_deletion == flag:
            return False
        self.marked_for_deletion = flag
        return True

    def mark_published(self, source_file: str, base_text: str | None = None) -> None:
        """Promote the published local value to production and update cell metadata."""
        self.prod_value = self.local_value
        self.source_file = source_file
        self.marked_for_deletion = False
        if self.local_value is None:
            self.kind = CellKind.MISSING
        elif self.kind != CellKind.ORPHAN:
            self._recompute_kind(base_text)

    def clear_after_deletion(self) -> None:
        """Reset cell state after its orphan key was removed from production."""
        self.prod_value = None
        self.local_value = None
        self.marked_for_deletion = False
        self.source_file = ""
        self.kind = CellKind.MISSING


@dataclass
class TableRowData:
    """Unified row representing one localization key across base and target languages."""

    key_path: str
    base_text: str | None
    base_source_file: str = ""
    base_line: int = 0
    is_orphan_row: bool = False
    cells: dict[str, CellData] = field(default_factory=dict)
    base_issues: list[ValidationIssue] = field(default_factory=list, compare=False, repr=False)
    _search_blob: str = field(default="", init=False, repr=False)

    def rebuild_search_blob(self) -> None:
        parts = [self.key_path.lower(), (self.base_text or "").lower()]
        for cell in self.cells.values():
            if cell.local_value:
                parts.append(cell.local_value.lower())
        self._search_blob = "\n".join(parts)

    def matches_search(self, query_lower: str) -> bool:
        if not self._search_blob:
            self.rebuild_search_blob()
        return query_lower in self._search_blob


@dataclass
class FileSnapshot:
    """Captured disk SHA-256 and string entries for a localization file."""

    sha256: str
    entries: dict[str, str] = field(default_factory=dict)


@dataclass
class LoadedFileInfo:
    """Loaded localization file together with its parsed diagnostics."""

    lang: str
    rel_path: str
    document: ParsedLangDocument | None
    conditional: str | None = None
    missing_on_disk: bool = False
    sha256: str = ""

    @property
    def has_fatal_error(self) -> bool:
        return self.missing_on_disk or (
            self.document is not None and self.document.fatal_error is not None
        )


@dataclass
class PackageSession:
    """Loaded package ready for table display and inspection."""

    manifest: ManifestInfo
    base_lang: str
    base_external_path: Path | None
    target_langs: list[str]
    files: list[LoadedFileInfo]
    rows: list[TableRowData]
    warnings: list[ManifestWarning]
    file_diagnostics: dict[str, list[DiagnosticIssue]] = field(default_factory=dict)
    lang_conditionals: dict[str, list[str]] = field(default_factory=dict)
    fatal_files_by_lang: dict[str, list[str]] = field(default_factory=dict)
    project_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    file_snapshots: dict[str, FileSnapshot] = field(default_factory=dict)
    project_path: Path | None = None
    enabled_paths: list[str] = field(default_factory=list)
    missing_target_mapping: dict[str, str] = field(default_factory=dict)
    pending_conflict_keys: set[tuple[str, str]] = field(default_factory=set)
    ignored_warnings: list[IgnoredWarning] = field(default_factory=list)
    custom_enrichers: list[CustomEnricherRule] = field(default_factory=list)
    project_glossary: list[GlossaryEntry] = field(default_factory=list)

    def has_ignored_warning(
        self,
        key_path: str,
        lang: str,
        rule_id: str,
        value_hash: str,
    ) -> bool:
        """Return True if an exception matching (key_path, lang, rule_id, value_hash) exists."""
        return any(
            iw.key_path == key_path
            and iw.lang == lang
            and iw.rule_id == rule_id
            and iw.value_hash == value_hash
            for iw in self.ignored_warnings
        )

    def set_ignored_warning(
        self,
        key_path: str,
        lang: str,
        rule_id: str,
        value_hash: str,
        *,
        ignore: bool,
        reason: str = "",
    ) -> None:
        """Add or remove a per-cell validation exception matching rule_id and current value_hash."""
        self.ignored_warnings = [
            iw
            for iw in self.ignored_warnings
            if not (iw.key_path == key_path and iw.lang == lang and iw.rule_id == rule_id)
        ]
        if ignore:
            self.ignored_warnings.append(
                IgnoredWarning(
                    key_path=key_path,
                    lang=lang,
                    rule_id=rule_id,
                    value_hash=value_hash,
                    reason=reason,
                )
            )


def cldr_categories_for_lang(lang: str) -> tuple[str, ...]:
    """Return required CLDR cardinal plural categories for a language tag."""
    primary = lang.split("-", 1)[0].lower()
    return _CLDR_CATEGORIES.get(primary, ("one", "other"))


def _format_conditional(raw_entry: dict[str, Any]) -> str | None:
    parts: list[str] = []
    if isinstance(raw_entry.get("system"), str) and raw_entry["system"].strip():
        parts.append(f"system: {raw_entry['system'].strip()}")
    if isinstance(raw_entry.get("module"), str) and raw_entry["module"].strip():
        parts.append(f"module: {raw_entry['module'].strip()}")
    return ", ".join(parts) if parts else None


def discover_manifest(manifest_path: Path) -> ManifestInfo:
    """Read module.json/system.json and validate its declared languages[] entries."""
    resolved_manifest = manifest_path.resolve()
    package_root = resolved_manifest.parent
    data = json.loads(resolved_manifest.read_text(encoding="utf-8-sig"))

    stem = resolved_manifest.stem.lower()
    manifest_type: Literal["module", "system"] = "system" if stem == "system" else "module"
    package_id = str(data.get("id") or package_root.name)

    entries: list[ManifestLangEntry] = []
    warnings: list[ManifestWarning] = []
    seen_lower: dict[str, str] = {}

    for raw in data.get("languages", []):
        if not isinstance(raw, dict):
            continue
        lang = str(raw.get("lang", "")).strip()
        path_str = str(raw.get("path", "")).strip()
        name = str(raw.get("name") or lang).strip()
        if not lang or not path_str:
            continue

        lower_lang = lang.lower()
        prev_lang = seen_lower.get(lower_lang)
        if prev_lang is not None and prev_lang != lang:
            warnings.append(
                ManifestWarning(
                    kind="case_collision",
                    lang=lang,
                    path=path_str,
                    message=f"Language tags '{prev_lang}' and '{lang}' differ only in case.",
                )
            )
        seen_lower.setdefault(lower_lang, lang)

        if not _BCP47_TAG_RE.match(lang):
            warnings.append(
                ManifestWarning(
                    kind="non_canonical_bcp47",
                    lang=lang,
                    path=path_str,
                    message=f"Language tag '{lang}' does not follow standard BCP-47 casing.",
                )
            )

        conditional = _format_conditional(raw)
        if path_str.startswith(("http://", "https://")):
            warnings.append(
                ManifestWarning(
                    kind="remote_http",
                    lang=lang,
                    path=path_str,
                    message=f"Remote HTTP language path '{path_str}' is read-only and ignored.",
                )
            )
            entries.append(
                ManifestLangEntry(
                    lang=lang,
                    name=name,
                    path=path_str,
                    editable=False,
                    is_http=True,
                    conditional=conditional,
                )
            )
            continue

        candidate = (package_root / path_str).resolve()
        if not candidate.is_relative_to(package_root):
            warnings.append(
                ManifestWarning(
                    kind="path_escape",
                    lang=lang,
                    path=path_str,
                    message=f"Language path '{path_str}' escapes package root and was rejected.",
                )
            )
            entries.append(
                ManifestLangEntry(
                    lang=lang,
                    name=name,
                    path=path_str,
                    editable=False,
                    conditional=conditional,
                )
            )
            continue

        entries.append(
            ManifestLangEntry(
                lang=lang,
                name=name,
                path=path_str.replace("\\", "/"),
                editable=True,
                conditional=conditional,
                resolved_path=candidate,
            )
        )

    editable_langs = [e.lang for e in entries if e.editable]
    default_base = "en" if "en" in editable_langs else (editable_langs[0] if editable_langs else "")

    return ManifestInfo(
        manifest_path=resolved_manifest,
        package_root=package_root,
        manifest_type=manifest_type,
        package_id=package_id,
        default_base_lang=default_base,
        entries=entries,
        warnings=warnings,
    )


def _load_single_file(
    lang: str,
    rel_path: str,
    file_path: Path,
    conditional: str | None = None,
) -> LoadedFileInfo:
    if not file_path.exists():
        return LoadedFileInfo(
            lang=lang,
            rel_path=rel_path,
            document=None,
            conditional=conditional,
            missing_on_disk=True,
        )
    raw_bytes = file_path.read_bytes()
    doc = parse_lang_bytes(raw_bytes, source_file=rel_path)
    return LoadedFileInfo(
        lang=lang,
        rel_path=rel_path,
        document=doc,
        conditional=conditional,
        missing_on_disk=False,
        sha256=hashlib.sha256(raw_bytes).hexdigest(),
    )


def _merge_lang_files(
    loaded: list[LoadedFileInfo],
    warnings: list[ManifestWarning],
) -> tuple[dict[str, LangEntry], list[str]]:
    merged: dict[str, LangEntry] = {}
    ordered_keys: list[str] = []
    seen_files: dict[str, str] = {}

    for item in loaded:
        if item.document is None or item.document.fatal_error is not None:
            continue
        for key in item.document.ordered_keys:
            entry = item.document.entries[key]
            if key in seen_files and seen_files[key] != item.rel_path:
                warnings.append(
                    ManifestWarning(
                        kind="multi_file_collision",
                        lang=item.lang,
                        path=item.rel_path,
                        key_path=key,
                        message=(
                            f"Key '{key}' in '{item.rel_path}' overrides earlier definition "
                            f"from '{seen_files[key]}'."
                        ),
                    )
                )
            else:
                ordered_keys.append(key)
            seen_files[key] = item.rel_path
            merged[key] = entry
    return merged, ordered_keys


def _find_plural_prefixes(ordered_keys: list[str]) -> dict[str, str]:
    """Identify base prefixes that use CLDR plural suffixes and return their fallback (.other/.one) key."""
    grouped: dict[str, dict[str, str]] = {}
    for key in ordered_keys:
        if "." not in key:
            continue
        prefix, suffix = key.rsplit(".", 1)
        if suffix in _PLURAL_SUFFIXES:
            grouped.setdefault(prefix, {})[suffix] = key

    prefixes: dict[str, str] = {}
    for prefix, suffixes in grouped.items():
        if len(suffixes) >= 2 or ("one" in suffixes and "other" in suffixes):
            ref_key = suffixes.get("other") or suffixes.get("one") or next(iter(suffixes.values()))
            prefixes[prefix] = ref_key
    return prefixes


def _has_structural_conflict(key_path: str, other_keys: set[str]) -> bool:
    """True if key_path is an ancestor or descendant of any key in other_keys."""
    parts = key_path.split(".")
    for i in range(1, len(parts)):
        if ".".join(parts[:i]) in other_keys:
            return True
    prefix = f"{key_path}."
    return any(k.startswith(prefix) for k in other_keys)


def load_package_session(
    manifest: ManifestInfo,
    base_lang: str | None = None,
    selected_entries: list[ManifestLangEntry] | None = None,
    base_external_path: Path | None = None,
) -> PackageSession:
    """Load selected package files and unify keys across base and target languages."""
    effective_base = base_lang or manifest.default_base_lang
    chosen = [
        e for e in (selected_entries if selected_entries is not None else manifest.entries) if e.editable
    ]

    warnings = list(manifest.warnings)
    loaded_files: list[LoadedFileInfo] = []
    file_diagnostics: dict[str, list[DiagnosticIssue]] = {}
    lang_conditionals: dict[str, list[str]] = {}
    fatal_files_by_lang: dict[str, list[str]] = {}

    if base_external_path is not None:
        ext_resolved = base_external_path.resolve()
        loaded_files.append(_load_single_file(effective_base, ext_resolved.name, ext_resolved))

    for entry in chosen:
        if entry.resolved_path is None:
            continue
        if base_external_path is not None and entry.lang == effective_base:
            continue
        loaded_files.append(
            _load_single_file(entry.lang, entry.path, entry.resolved_path, conditional=entry.conditional)
        )
        if entry.conditional:
            lang_conditionals.setdefault(entry.lang, [])
            if entry.conditional not in lang_conditionals[entry.lang]:
                lang_conditionals[entry.lang].append(entry.conditional)

    by_lang: dict[str, list[LoadedFileInfo]] = {}
    for lf in loaded_files:
        by_lang.setdefault(lf.lang, []).append(lf)
        if lf.missing_on_disk:
            fatal_files_by_lang.setdefault(lf.lang, []).append(lf.rel_path)
            warnings.append(
                ManifestWarning(
                    kind="missing_file",
                    lang=lf.lang,
                    path=lf.rel_path,
                    message=f"File '{lf.rel_path}' not found on disk.",
                )
            )
            continue
        if lf.document is not None:
            issues: list[DiagnosticIssue] = []
            if lf.document.fatal_error is not None:
                issues.append(lf.document.fatal_error)
                fatal_files_by_lang.setdefault(lf.lang, []).append(lf.rel_path)
                warnings.append(
                    ManifestWarning(
                        kind="fatal_file",
                        lang=lf.lang,
                        path=lf.rel_path,
                        message=lf.document.fatal_error.message,
                    )
                )
            issues.extend(lf.document.duplicates)
            issues.extend(lf.document.overwrites)
            issues.extend(lf.document.non_string_keys)
            if issues:
                file_diagnostics[lf.rel_path] = issues

    base_merged, base_order = _merge_lang_files(by_lang.get(effective_base, []), warnings)
    target_langs = [lang for lang in by_lang.keys() if lang != effective_base]

    target_merged: dict[str, dict[str, LangEntry]] = {}
    target_orders: dict[str, list[str]] = {}
    for t_lang in target_langs:
        t_entries, t_order = _merge_lang_files(by_lang[t_lang], warnings)
        target_merged[t_lang] = t_entries
        target_orders[t_lang] = t_order

    plural_prefixes = _find_plural_prefixes(base_order)
    base_key_set = set(base_merged.keys())
    target_key_sets = {lang: set(entries.keys()) for lang, entries in target_merged.items()}

    # CLDR calculado POR IDIOMA para não vazar categorias (ex.: .many) para idiomas sem ela (ex.: de)
    valid_cldr_by_lang: dict[str, set[str]] = {t_lang: set() for t_lang in target_langs}
    unified_keys: list[str] = []
    seen_unified: set[str] = set()
    plural_ref_for_key: dict[str, str] = {}

    for key in base_order:
        if key not in seen_unified:
            unified_keys.append(key)
            seen_unified.add(key)

    for prefix, ref_key in plural_prefixes.items():
        needed_suffixes: list[str] = []
        for t_lang in target_langs:
            for cat in cldr_categories_for_lang(t_lang):
                cand = f"{prefix}.{cat}"
                valid_cldr_by_lang[t_lang].add(cand)
                if cand not in seen_unified and cand not in needed_suffixes:
                    needed_suffixes.append(cand)
        if needed_suffixes:
            insert_at = max(
                (i for i, k in enumerate(unified_keys) if k.startswith(f"{prefix}.")),
                default=len(unified_keys) - 1,
            ) + 1
            for offset, cand in enumerate(needed_suffixes):
                unified_keys.insert(insert_at + offset, cand)
                seen_unified.add(cand)
                plural_ref_for_key[cand] = ref_key

    # Chaves órfãs: ausentes da base e NÃO válidas no CLDR daquele idioma específico
    orphan_keys: list[str] = []
    for t_lang in target_langs:
        valid_for_lang = valid_cldr_by_lang[t_lang]
        for t_key in target_orders[t_lang]:
            if t_key not in base_key_set and t_key not in valid_for_lang and t_key not in seen_unified:
                orphan_keys.append(t_key)
                seen_unified.add(t_key)

    rows: list[TableRowData] = []
    for key in unified_keys:
        base_entry = base_merged.get(key)
        plural_ref_key: str | None = plural_ref_for_key.get(key)
        ref_entry = base_merged.get(plural_ref_key) if plural_ref_key else None
        effective_base_entry = base_entry or ref_entry
        base_text = effective_base_entry.value if effective_base_entry and effective_base_entry.is_string else None

        row = TableRowData(
            key_path=key,
            base_text=base_text,
            base_source_file=effective_base_entry.source_file if effective_base_entry else "",
            base_line=effective_base_entry.line if effective_base_entry else 0,
            is_orphan_row=False,
        )
        for t_lang in target_langs:
            applies_to_lang = (key in base_key_set) or (key in valid_cldr_by_lang[t_lang])
            row.cells[t_lang] = _build_target_cell(
                key=key,
                base_text=base_text,
                base_exists=applies_to_lang,
                applies_to_lang=applies_to_lang,
                target_entry=target_merged[t_lang].get(key),
                target_key_set=target_key_sets[t_lang],
                is_plural_suggestion=(plural_ref_key is not None and applies_to_lang),
                lang_has_fatal=(t_lang in fatal_files_by_lang),
            )
        rows.append(row)

    for key in orphan_keys:
        row = TableRowData(key_path=key, base_text=None, is_orphan_row=True)
        for t_lang in target_langs:
            t_entry = target_merged[t_lang].get(key)
            if t_entry is None:
                row.cells[t_lang] = CellData(
                    prod_value=None,
                    local_value=None,
                    kind=CellKind.NOT_APPLICABLE,
                    readonly=True,
                )
            elif not t_entry.is_string:
                row.cells[t_lang] = CellData(
                    prod_value=None,
                    local_value=None,
                    kind=CellKind.NON_STRING,
                    source_file=t_entry.source_file,
                    line=t_entry.line,
                    raw_type=t_entry.raw_type,
                    readonly=True,
                )
            elif _has_structural_conflict(key, base_key_set):
                row.cells[t_lang] = CellData(
                    prod_value=t_entry.value,
                    local_value=t_entry.value,
                    kind=CellKind.STRUCTURAL_CONFLICT,
                    source_file=t_entry.source_file,
                    line=t_entry.line,
                    readonly=True,
                )
            else:
                row.cells[t_lang] = CellData(
                    prod_value=t_entry.value,
                    local_value=t_entry.value,
                    kind=CellKind.ORPHAN,
                    source_file=t_entry.source_file,
                    line=t_entry.line,
                )
        rows.append(row)

    file_snapshots: dict[str, FileSnapshot] = {}
    for lf in loaded_files:
        if lf.document is not None and lf.document.fatal_error is None:
            file_snapshots[lf.rel_path] = FileSnapshot(
                sha256=lf.sha256,
                entries={
                    k: e.value
                    for k, e in lf.document.entries.items()
                    if e.is_string and e.value is not None
                },
            )

    return PackageSession(
        manifest=manifest,
        base_lang=effective_base,
        base_external_path=base_external_path,
        target_langs=target_langs,
        files=loaded_files,
        rows=rows,
        warnings=warnings,
        file_diagnostics=file_diagnostics,
        lang_conditionals=lang_conditionals,
        fatal_files_by_lang=fatal_files_by_lang,
        file_snapshots=file_snapshots,
        enabled_paths=[e.path for e in chosen],
    )


def _build_target_cell(
    key: str,
    base_text: str | None,
    base_exists: bool,
    applies_to_lang: bool,
    target_entry: LangEntry | None,
    target_key_set: set[str],
    is_plural_suggestion: bool,
    lang_has_fatal: bool,
) -> CellData:
    if target_entry is None:
        if not applies_to_lang:
            return CellData(
                prod_value=None,
                local_value=None,
                kind=CellKind.NOT_APPLICABLE,
                readonly=True,
            )
        if _has_structural_conflict(key, target_key_set):
            return CellData(
                prod_value=None,
                local_value=None,
                kind=CellKind.STRUCTURAL_CONFLICT,
                readonly=True,
            )
        return CellData(
            prod_value=None,
            local_value=None,
            kind=CellKind.MISSING,
            readonly=lang_has_fatal,
            is_plural_suggestion=is_plural_suggestion,
        )

    if not target_entry.is_string:
        return CellData(
            prod_value=None,
            local_value=None,
            kind=CellKind.NON_STRING,
            source_file=target_entry.source_file,
            line=target_entry.line,
            raw_type=target_entry.raw_type,
            readonly=True,
        )

    if not applies_to_lang:
        # Existe no arquivo de destino mas não na base e nem no CLDR deste idioma (ex.: .many espúrio em 'de')
        return CellData(
            prod_value=target_entry.value,
            local_value=target_entry.value,
            kind=CellKind.ORPHAN,
            source_file=target_entry.source_file,
            line=target_entry.line,
            readonly=lang_has_fatal,
        )

    val: str = target_entry.value if target_entry.value is not None else ""
    if val == "":
        kind = CellKind.EMPTY
    elif base_exists and base_text is not None and val == base_text:
        kind = CellKind.SAME_AS_BASE
    else:
        kind = CellKind.TRANSLATED

    return CellData(
        prod_value=val,
        local_value=val,
        kind=kind,
        source_file=target_entry.source_file,
        line=target_entry.line,
        readonly=lang_has_fatal,
        is_plural_suggestion=is_plural_suggestion,
    )


from app.core.project_storage import (  # noqa: E402, F401
    CURRENT_SCHEMA_VERSION,
    ConflictChoice,
    ConflictResolution,
    LoadedProjectResult,
    PackageNotFoundError,
    SyncConflict,
    SyncPreview,
    SyncReport,
    UnsupportedProjectVersionError,
    apply_conflict_resolutions,
    atomic_write_text,
    check_external_disk_changes,
    clear_recovery_draft,
    commit_sync_preview,
    default_app_data_dir,
    has_recovery_draft,
    load_project_file,
    prepare_disk_sync,
    resolve_loaded_file_path,
    save_project_file,
    synchronize_session_with_disk,
    write_recovery_draft,
)
