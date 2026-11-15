from __future__ import annotations

from dataclasses import dataclass
import re

from app.core.glossary import technical_char_mask
from app.core.validator import CustomEnricherRule


@dataclass(frozen=True)
class TextReplaceResult:
    """Outcome of replacing eligible occurrences in a single cell string."""

    new_text: str
    eligible_count: int
    skipped_protected_count: int


def compile_find_pattern(
    query: str,
    *,
    case_sensitive: bool = False,
    whole_word: bool = False,
) -> re.Pattern[str] | None:
    """Compile a literal search regex respecting case-sensitivity and whole-word boundaries."""
    if not query:
        return None
    flags = 0 if case_sensitive else re.IGNORECASE
    escaped = re.escape(query)
    if whole_word:
        prefix = r"(?<!\w)" if (query[0].isalnum() or query[0] == "_") else ""
        suffix = r"(?!\w)" if (query[-1].isalnum() or query[-1] == "_") else ""
        escaped = f"{prefix}{escaped}{suffix}"
    return re.compile(escaped, flags)


def find_matches_in_text(
    text: str,
    pattern: re.Pattern[str],
    *,
    protect_tokens: bool = True,
    custom_enrichers: list[CustomEnricherRule] | None = None,
) -> tuple[list[tuple[int, int]], int]:
    """Return (eligible_spans, skipped_protected_count) for pattern matches in text."""
    if not text:
        return [], 0
    mask = technical_char_mask(text, custom_enrichers=custom_enrichers) if protect_tokens else []
    eligible: list[tuple[int, int]] = []
    skipped = 0
    for match in pattern.finditer(text):
        start, end = match.span()
        if end <= start:
            continue
        if protect_tokens and any(mask[start:end]):
            skipped += 1
            continue
        eligible.append((start, end))
    return eligible, skipped


def replace_first_in_text(
    text: str,
    pattern: re.Pattern[str],
    replacement: str,
    *,
    start_pos: int = 0,
    protect_tokens: bool = True,
    custom_enrichers: list[CustomEnricherRule] | None = None,
) -> tuple[str, tuple[int, int] | None, int]:
    """Replace the first eligible match at or after start_pos, returning (new_text, replaced_span, skipped)."""
    eligible, skipped = find_matches_in_text(
        text,
        pattern,
        protect_tokens=protect_tokens,
        custom_enrichers=custom_enrichers,
    )
    for start, end in eligible:
        if start >= start_pos:
            new_text = text[:start] + replacement + text[end:]
            return new_text, (start, start + len(replacement)), skipped
    return text, None, skipped


def replace_all_in_text(
    text: str,
    pattern: re.Pattern[str],
    replacement: str,
    *,
    protect_tokens: bool = True,
    custom_enrichers: list[CustomEnricherRule] | None = None,
) -> TextReplaceResult:
    """Replace all eligible matches in text while preserving protected technical spans."""
    eligible, skipped = find_matches_in_text(
        text,
        pattern,
        protect_tokens=protect_tokens,
        custom_enrichers=custom_enrichers,
    )
    if not eligible:
        return TextReplaceResult(new_text=text, eligible_count=0, skipped_protected_count=skipped)

    parts: list[str] = []
    cursor = 0
    for start, end in eligible:
        parts.append(text[cursor:start])
        parts.append(replacement)
        cursor = end
    parts.append(text[cursor:])
    return TextReplaceResult(
        new_text="".join(parts),
        eligible_count=len(eligible),
        skipped_protected_count=skipped,
    )
