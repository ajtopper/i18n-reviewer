from __future__ import annotations

import csv
from dataclasses import dataclass, field
import io
import json
import os
from pathlib import Path
import re
from typing import Any

from app.core.validator import (
    CustomEnricherRule,
    IgnoredWarning,
    ValidationIssue,
    build_ignored_map,
    default_app_data_dir,
    extract_protected_tokens,
    term_boundary_pattern,
)


@dataclass(frozen=True)
class GlossaryEntry:
    """Single glossary term with source variants, translation variants per language, and linter flags."""

    term: str
    source_variants: list[str] = field(default_factory=list)
    case_sensitive: bool = False
    do_not_translate: bool = False
    notes: str = ""
    translations: dict[str, list[str]] = field(default_factory=dict)

    def accepted_translations(self, lang: str) -> list[str]:
        """Return all accepted target renderings for a language (or original term if DNT)."""
        if self.do_not_translate:
            return [self.term]
        return list(self.translations.get(lang, []))

    def preferred_translation(self, lang: str) -> str | None:
        """Return preferred translation for a language, or None if unavailable."""
        opts = self.accepted_translations(lang)
        return opts[0] if opts else None


def global_glossary_path(app_data_dir: Path | None = None) -> Path:
    """Return path to the user-wide global glossary JSON under %APPDATA%."""
    base = app_data_dir or default_app_data_dir()
    return base / "glossary.json"


def _atomic_write_utf8(target: Path, text: str, *, encoding: str = "utf-8") -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = target.with_name(f"{target.name}.tmp")
    tmp_path.write_text(text, encoding=encoding)
    os.replace(tmp_path, target)


def serialize_glossary_entries(entries: list[GlossaryEntry]) -> list[dict[str, Any]]:
    """Convert GlossaryEntry objects into JSON-serializable dictionaries."""
    return [
        {
            "term": e.term,
            "source_variants": list(e.source_variants),
            "case_sensitive": e.case_sensitive,
            "do_not_translate": e.do_not_translate,
            "notes": e.notes,
            "translations": {lang: list(vals) for lang, vals in e.translations.items()},
        }
        for e in entries
    ]


def deserialize_glossary_entries(raw_items: object) -> list[GlossaryEntry]:
    """Parse JSON list of glossary dictionaries into GlossaryEntry instances."""
    if not isinstance(raw_items, list):
        return []
    entries: list[GlossaryEntry] = []
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        term = str(item.get("term", "")).strip()
        if not term:
            continue
        raw_variants = item.get("source_variants", [])
        source_variants = (
            [str(v).strip() for v in raw_variants if str(v).strip()]
            if isinstance(raw_variants, list)
            else []
        )
        raw_trans = item.get("translations", {})
        translations: dict[str, list[str]] = {}
        if isinstance(raw_trans, dict):
            for lang, vals in raw_trans.items():
                if isinstance(vals, list):
                    cleaned = [str(v).strip() for v in vals if str(v).strip()]
                    if cleaned:
                        translations[str(lang)] = cleaned
        entries.append(
            GlossaryEntry(
                term=term,
                source_variants=source_variants,
                case_sensitive=bool(item.get("case_sensitive", False)),
                do_not_translate=bool(item.get("do_not_translate", False)),
                notes=str(item.get("notes", "") or ""),
                translations=translations,
            )
        )
    return entries


def load_global_glossary(app_data_dir: Path | None = None) -> list[GlossaryEntry]:
    """Load the user-wide global glossary from glossary.json (empty list if missing)."""
    path = global_glossary_path(app_data_dir)
    if not path.exists():
        return []
    return import_glossary_json(path)


def save_global_glossary(
    entries: list[GlossaryEntry],
    app_data_dir: Path | None = None,
) -> Path:
    """Persist global glossary entries atomically to glossary.json."""
    path = global_glossary_path(app_data_dir)
    export_glossary_json(entries, path)
    return path


def _merge_key(entry: GlossaryEntry) -> str:
    return entry.term if entry.case_sensitive else entry.term.casefold()


def merge_glossaries(
    global_entries: list[GlossaryEntry],
    project_entries: list[GlossaryEntry],
) -> list[GlossaryEntry]:
    """Combine global and project glossaries, with project entries overriding matching global terms."""
    merged: dict[str, GlossaryEntry] = {}
    project_casefold_keys = {e.term.casefold() for e in project_entries if not e.case_sensitive}

    for g_entry in global_entries:
        g_key = (
            g_entry.term
            if (g_entry.case_sensitive and g_entry.term.casefold() not in project_casefold_keys)
            else g_entry.term.casefold()
        )
        merged[g_key] = g_entry

    for p_entry in project_entries:
        p_key = _merge_key(p_entry)
        if not p_entry.case_sensitive:
            for existing_k in [k for k in merged if k.casefold() == p_entry.term.casefold()]:
                del merged[existing_k]
        elif p_entry.term.casefold() in merged:
            del merged[p_entry.term.casefold()]
        merged[p_key] = p_entry

    return list(merged.values())


def export_glossary_json(entries: list[GlossaryEntry], path: Path) -> None:
    """Export glossary entries to a structured UTF-8 JSON file."""
    payload = {"schema_version": 1, "entries": serialize_glossary_entries(entries)}
    _atomic_write_utf8(path, json.dumps(payload, indent=2, ensure_ascii=False) + "\n")


def import_glossary_json(path: Path) -> list[GlossaryEntry]:
    """Import glossary entries from JSON (supports wrapper object or top-level list)."""
    raw = json.loads(path.read_text(encoding="utf-8-sig"))
    if isinstance(raw, dict):
        return deserialize_glossary_entries(raw.get("entries", []))
    return deserialize_glossary_entries(raw)


def export_glossary_csv(entries: list[GlossaryEntry], path: Path) -> None:
    """Export glossary entries to UTF-8 CSV with per-language translation columns (`trans:<lang>`)."""
    langs = sorted({lang for e in entries for lang in e.translations})
    fieldnames = ["term", "source_variants", "case_sensitive", "do_not_translate", "notes"] + [
        f"trans:{lang}" for lang in langs
    ]
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fieldnames)
    writer.writeheader()
    for entry in entries:
        row: dict[str, str] = {
            "term": entry.term,
            "source_variants": " | ".join(entry.source_variants),
            "case_sensitive": "true" if entry.case_sensitive else "false",
            "do_not_translate": "true" if entry.do_not_translate else "false",
            "notes": entry.notes,
        }
        for lang in langs:
            vals = entry.translations.get(lang, [])
            if vals:
                row[f"trans:{lang}"] = " | ".join(vals)
        writer.writerow(row)
    _atomic_write_utf8(path, buf.getvalue(), encoding="utf-8-sig")


def _parse_bool_cell(val: object) -> bool:
    return str(val or "").strip().lower() in ("1", "true", "yes", "sim", "on")


def import_glossary_csv(path: Path) -> list[GlossaryEntry]:
    """Import glossary entries from CSV exported by export_glossary_csv."""
    entries: list[GlossaryEntry] = []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            term = str(row.get("term") or "").strip()
            if not term:
                continue
            src_raw = str(row.get("source_variants") or "")
            source_variants = [s.strip() for s in src_raw.split("|") if s.strip()]
            translations: dict[str, list[str]] = {}
            for col_name, cell_val in row.items():
                if col_name and col_name.startswith("trans:") and cell_val:
                    lang = col_name[len("trans:") :].strip()
                    variants = [v.strip() for v in str(cell_val).split("|") if v.strip()]
                    if lang and variants:
                        translations[lang] = variants
            entries.append(
                GlossaryEntry(
                    term=term,
                    source_variants=source_variants,
                    case_sensitive=_parse_bool_cell(row.get("case_sensitive")),
                    do_not_translate=_parse_bool_cell(row.get("do_not_translate")),
                    notes=str(row.get("notes") or ""),
                    translations=translations,
                )
            )
    return entries


def _unmask_enricher_part(chars: list[str], tok_start: int, raw: str, part: str) -> None:
    """Locate translatable part inside its syntactic slot rather than anywhere in technical body."""
    if not part:
        return
    # 1) Trailing {label} after closing bracket
    suffix = "{" + part + "}"
    if raw.endswith(suffix):
        rel = len(raw) - len(part) - 1
        for offset, ch in enumerate(part):
            chars[tok_start + rel + offset] = ch
        return
    # 2) @Embed caption="..." or @Check name:... or [[... #flavor]]
    for pat in (
        re.compile(r'\bcaption\s*=\s*["\'](' + re.escape(part) + r')["\']', re.IGNORECASE),
        re.compile(r'\bname\s*:\s*["\']?(' + re.escape(part) + r')["\']?(?=[|\]])', re.IGNORECASE),
        re.compile(r'\s#(' + re.escape(part) + r')\s*\]\]'),
    ):
        m = pat.search(raw)
        if m:
            for offset, ch in enumerate(part):
                chars[tok_start + m.start(1) + offset] = ch
            return


def mask_technical_spans(
    text: str,
    custom_enrichers: list[CustomEnricherRule] | None = None,
) -> str:
    """Replace technical spans extracted by Ticket 05 with spaces while preserving translatable labels."""
    if not text:
        return ""
    tokens = extract_protected_tokens(text, custom_enrichers=custom_enrichers)
    chars = list(text)
    for tok in tokens:
        for idx in range(tok.start, tok.end):
            chars[idx] = " "
        if tok.kind == "enricher":
            for part in tok.translatable_parts:
                _unmask_enricher_part(chars, tok.start, tok.raw, part)
    return "".join(chars)


def mask_glossary_phrases(
    masked_text: str,
    lang: str,
    entries: list[GlossaryEntry],
) -> str:
    """Replace active glossary phrases (source and target accepted variants) with spaces."""
    if not masked_text or not entries:
        return masked_text
    chars = list(masked_text)
    for entry in entries:
        phrases = [entry.term, *entry.source_variants, *entry.accepted_translations(lang)]
        for phrase in phrases:
            clean = phrase.strip()
            if not clean:
                continue
            pat = term_boundary_pattern(clean, case_sensitive=entry.case_sensitive)
            for m in pat.finditer(masked_text):
                for idx in range(m.start(), m.end()):
                    chars[idx] = " "
    return "".join(chars)


def detect_base_glossary_matches(
    base_text: str | None,
    entries: list[GlossaryEntry],
    *,
    custom_enrichers: list[CustomEnricherRule] | None = None,
) -> list[GlossaryEntry]:
    """Find non-overlapping glossary entries in masked base text (longest match wins)."""
    if not base_text or not entries:
        return []
    masked = mask_technical_spans(base_text, custom_enrichers=custom_enrichers)
    candidates: list[tuple[int, int, int, GlossaryEntry]] = []

    for entry_idx, entry in enumerate(entries):
        phrases = [entry.term, *entry.source_variants]
        seen_phrases: set[str] = set()
        for phrase in phrases:
            clean = phrase.strip()
            if not clean or clean in seen_phrases:
                continue
            seen_phrases.add(clean)
            for m in term_boundary_pattern(clean, case_sensitive=entry.case_sensitive).finditer(masked):
                s, e = m.span()
                candidates.append((-(e - s), s, entry_idx, entry))

    candidates.sort(key=lambda item: (item[0], item[1], item[2]))
    occupied = [False] * len(masked)
    winning: list[tuple[int, GlossaryEntry]] = []
    seen_entry_ids: set[int] = set()

    for neg_len, start, entry_idx, entry in candidates:
        end = start - neg_len
        if any(occupied[start:end]):
            continue
        for pos in range(start, end):
            occupied[pos] = True
        if id(entry) not in seen_entry_ids:
            seen_entry_ids.add(id(entry))
            winning.append((start, entry))

    winning.sort(key=lambda item: item[0])
    return [entry for _, entry in winning]


def lint_translation_glossary(
    key_path: str,
    lang: str,
    base_text: str | None,
    target_text: str | None,
    entries: list[GlossaryEntry],
    *,
    custom_enrichers: list[CustomEnricherRule] | None = None,
    ignored_warnings: list[IgnoredWarning] | None = None,
) -> list[ValidationIssue]:
    """Check translated text against base glossary terms, returning non-blocking warning issues."""
    if not base_text or not target_text or not entries:
        return []

    matched = detect_base_glossary_matches(base_text, entries, custom_enrichers=custom_enrichers)
    if not matched:
        return []

    masked_target = mask_technical_spans(target_text, custom_enrichers=custom_enrichers)
    ignored_map = build_ignored_map(ignored_warnings, key_path, lang, target_text)
    issues: list[ValidationIssue] = []

    for entry in matched:
        accepted = entry.accepted_translations(lang)
        if not accepted:
            continue

        found = any(
            term_boundary_pattern(opt, case_sensitive=entry.case_sensitive).search(masked_target)
            is not None
            for opt in accepted
        )
        if found:
            continue

        rule_id = f"glossary:{entry.term}"
        ignored = ignored_map.get(rule_id)
        if entry.do_not_translate:
            msg = f"Do-not-translate term '{entry.term}' is missing or altered."
        else:
            msg = f"Glossary term '{entry.term}' expected as: {', '.join(accepted)}."
        issues.append(
            ValidationIssue(
                rule_id=rule_id,
                severity="warning",
                message=msg,
                missing_tokens=[accepted[0]],
                is_ignored=ignored is not None,
                ignored_reason=ignored.reason if ignored is not None else "",
            )
        )

    return issues
