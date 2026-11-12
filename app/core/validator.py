from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
import hashlib
import re
from typing import Literal

TokenKind = Literal["handlebars", "enricher", "url", "html", "placeholder"]
IssueSeverity = Literal["critical", "warning", "info"]

_HANDLEBARS_RE = re.compile(r"\{\{\{[\s\S]*?\}\}\}|\{\{[\s\S]*?\}\}")
_URL_RE = re.compile(r"https?://[^\s<>\"'`\)\]]+")
_HTML_TAG_RE = re.compile(r"<(/?)([A-Za-z][A-Za-z0-9:_-]*)(\s+[^<>]*)?(/?)>")
_HTML_ENTITY_RE = re.compile(r"&(?:#\d+|#x[0-9a-fA-F]+|[A-Za-z][A-Za-z0-9]+);")
_PLACEHOLDER_RE = re.compile(r"\{([A-Za-z0-9_.:-]+)\}")
_ATTR_RE = re.compile(r"""([A-Za-z_:][A-Za-z0-9_.:-]*)\s*(?:=\s*(?:"([^"]*)"|'([^']*)'|([^\s"'=<>`]+)))?""")
_URL_IN_ATTR_RE = re.compile(r"https?://\S+")
_BRACKET_ENRICHER_RE = re.compile(r"([@&])([A-Za-z_][A-Za-z0-9_-]*)\[")

_EMBED_CAPTION_RE = re.compile(r"""(\bcaption\s*=\s*)(?:"([^"]*)"|'([^']*)')""", re.IGNORECASE)
_CHECK_NAME_QUOTED_RE = re.compile(r"""(\bname\s*:\s*)(?:"([^"]*)"|'([^']*)')""", re.IGNORECASE)
_CHECK_NAME_PIPE_RE = re.compile(r"""(\bname\s*:\s*)([^|\]]+)""", re.IGNORECASE)
_INLINE_FLAVOR_RE = re.compile(r"^(.*?)\s+#([^#\]\n]+?)\s*$")

_KNOWN_BRACKET_ENRICHERS = frozenset(
    {
        "uuid",
        "embed",
        "localize",
        "compendium",
        "actor",
        "item",
        "journalentry",
        "rolltable",
        "scene",
        "macro",
        "playlist",
        "playlistsound",
        "reference",
        "check",
        "damage",
        "template",
    }
)
_KNOWN_INLINE_COMMANDS = frozenset(
    {
        "/r",
        "/roll",
        "/gmroll",
        "/blindroll",
        "/selfroll",
        "/attack",
        "/damage",
        "/save",
        "/check",
        "/heal",
        "/award",
        "/act",
    }
)
_TRANSLATABLE_HTML_ATTRS = frozenset({"title", "alt", "placeholder", "aria-label"})
_VOID_HTML_TAGS = frozenset(
    {
        "area",
        "base",
        "br",
        "col",
        "embed",
        "hr",
        "img",
        "input",
        "link",
        "meta",
        "param",
        "source",
        "track",
        "wbr",
    }
)


@dataclass(frozen=True)
class ProtectedToken:
    """Extracted protected span classified by cascade stage."""

    kind: TokenKind
    start: int
    end: int
    raw: str
    tech_key: str
    translatable_parts: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class CustomEnricherRule:
    """User-defined project regex rule for custom enrichers."""

    name: str
    pattern: str


@dataclass(frozen=True)
class IgnoredWarning:
    """Persisted exception suppressing a specific validation rule while value_hash matches."""

    key_path: str
    lang: str
    rule_id: str
    value_hash: str
    reason: str = ""


@dataclass
class ValidationIssue:
    """Single validation alert raised for a translated cell or base source string."""

    rule_id: str
    severity: IssueSeverity
    message: str
    missing_tokens: list[str] = field(default_factory=list)
    is_ignored: bool = False
    ignored_reason: str = ""


@dataclass(frozen=True)
class _IgnoreContext:
    ignored_warnings: list[IgnoredWarning]
    key_path: str
    lang: str
    value_hash: str

    def find(self, rule_id: str) -> IgnoredWarning | None:
        for item in self.ignored_warnings:
            if (
                item.key_path == self.key_path
                and item.lang == self.lang
                and item.rule_id == rule_id
                and item.value_hash == self.value_hash
            ):
                return item
        return None


def compute_value_hash(text: str | None) -> str:
    """Return a deterministic SHA-256 hash of a cell text for exception invalidation."""
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def _range_free(occupied: list[bool], start: int, end: int) -> bool:
    return not any(occupied[start:end])


def _mark_occupied(occupied: list[bool], start: int, end: int) -> None:
    for idx in range(max(0, start), min(len(occupied), end)):
        occupied[idx] = True


def _read_optional_brace_label(text: str, pos: int) -> tuple[str | None, int]:
    """Consume an immediate balanced `{label}` suffix after an enricher closing bracket."""
    if pos >= len(text) or text[pos] != "{":
        return None, pos
    depth = 1
    cursor = pos + 1
    while cursor < len(text) and depth > 0:
        if text[cursor] == "{":
            depth += 1
        elif text[cursor] == "}":
            depth -= 1
        cursor += 1
    if depth != 0:
        return None, pos
    return text[pos + 1 : cursor - 1], cursor


def _split_inline_roll(body: str, label: str | None) -> tuple[str, list[str]]:
    trans: list[str] = []
    clean_body = body
    flavor_match = _INLINE_FLAVOR_RE.match(body)
    if flavor_match:
        clean_body = flavor_match.group(1).strip()
        flavor = flavor_match.group(2).strip()
        if flavor:
            trans.append(flavor)
    else:
        clean_body = body.strip()
    if label is not None:
        trans.append(label)
    return f"[[{clean_body}]]", trans


def _split_at_or_amp_enricher(
    prefix: str,
    name: str,
    inner: str,
    label: str | None,
) -> tuple[str, list[str]]:
    trans: list[str] = []
    tech_inner = inner
    lower_name = name.lower()

    if lower_name == "embed":
        def _cap_sub(match: re.Match[str]) -> str:
            cap_val = match.group(2) if match.group(2) is not None else (match.group(3) or "")
            trans.append(cap_val)
            return f'{match.group(1)}""'

        tech_inner = _EMBED_CAPTION_RE.sub(_cap_sub, tech_inner)
    elif lower_name == "check":
        if _CHECK_NAME_QUOTED_RE.search(tech_inner):
            def _qname_sub(match: re.Match[str]) -> str:
                val = match.group(2) if match.group(2) is not None else (match.group(3) or "")
                trans.append(val.strip())
                return f"{match.group(1)}"

            tech_inner = _CHECK_NAME_QUOTED_RE.sub(_qname_sub, tech_inner)
        else:
            def _pname_sub(match: re.Match[str]) -> str:
                trans.append(match.group(2).strip())
                return f"{match.group(1)}"

            tech_inner = _CHECK_NAME_PIPE_RE.sub(_pname_sub, tech_inner)

    if label is not None:
        trans.append(label)

    tech_inner_norm = " ".join(tech_inner.split())
    return f"{prefix}{name}[{tech_inner_norm}]", trans


def _is_known_inline_roll(body: str) -> bool:
    stripped = body.strip()
    if not stripped:
        return False
    first_tok = stripped.split(None, 1)[0].lower()
    if first_tok.startswith("/"):
        return first_tok in _KNOWN_INLINE_COMMANDS
    return True


def _scan_inline_rolls(
    text: str,
    occupied: list[bool],
    *,
    known_only: bool,
) -> list[ProtectedToken]:
    tokens: list[ProtectedToken] = []
    idx = 0
    length = len(text)
    while idx < length - 3:
        if text[idx : idx + 2] == "[[" and not occupied[idx]:
            pos = idx + 2
            bracket_depth = 0
            end_pos = -1
            while pos < length - 1:
                ch = text[pos]
                if ch == "[":
                    bracket_depth += 1
                elif ch == "]":
                    if bracket_depth == 0 and text[pos + 1] == "]":
                        end_pos = pos + 2
                        break
                    if bracket_depth > 0:
                        bracket_depth -= 1
                pos += 1
            if end_pos != -1 and _range_free(occupied, idx, end_pos):
                body = text[idx + 2 : end_pos - 2]
                is_known = _is_known_inline_roll(body)
                if (known_only and not is_known) or (not known_only and is_known):
                    idx = end_pos
                    continue
                label, total_end = _read_optional_brace_label(text, end_pos)
                if _range_free(occupied, idx, total_end):
                    tech_key, trans = _split_inline_roll(body, label)
                    tokens.append(
                        ProtectedToken(
                            kind="enricher",
                            start=idx,
                            end=total_end,
                            raw=text[idx:total_end],
                            tech_key=tech_key,
                            translatable_parts=trans,
                        )
                    )
                    _mark_occupied(occupied, idx, total_end)
                    idx = total_end
                    continue
        idx += 1
    return tokens


def _scan_bracket_enrichers(
    text: str,
    occupied: list[bool],
    *,
    known_only: bool,
) -> list[ProtectedToken]:
    tokens: list[ProtectedToken] = []
    pos = 0
    while True:
        match = _BRACKET_ENRICHER_RE.search(text, pos)
        if not match:
            break
        start = match.start()
        if occupied[start]:
            pos = start + 1
            continue
        cursor = match.end()
        depth = 1
        while cursor < len(text) and depth > 0:
            if text[cursor] == "[":
                depth += 1
            elif text[cursor] == "]":
                depth -= 1
            cursor += 1
        if depth != 0:
            pos = match.end()
            continue
        name = match.group(2)
        is_known = name.lower() in _KNOWN_BRACKET_ENRICHERS
        if (known_only and not is_known) or (not known_only and is_known):
            pos = cursor
            continue
        inner = text[match.end() : cursor - 1]
        label, total_end = _read_optional_brace_label(text, cursor)
        if not _range_free(occupied, start, total_end):
            pos = start + 1
            continue
        tech_key, trans = _split_at_or_amp_enricher(
            match.group(1),
            name,
            inner,
            label,
        )
        tokens.append(
            ProtectedToken(
                kind="enricher",
                start=start,
                end=total_end,
                raw=text[start:total_end],
                tech_key=tech_key,
                translatable_parts=trans,
            )
        )
        _mark_occupied(occupied, start, total_end)
        pos = total_end
    return tokens


def _scan_custom_enrichers(
    text: str,
    occupied: list[bool],
    custom_enrichers: list[CustomEnricherRule],
) -> list[ProtectedToken]:
    tokens: list[ProtectedToken] = []
    for rule in custom_enrichers:
        if not rule.pattern:
            continue
        try:
            compiled = re.compile(rule.pattern)
        except re.error:
            continue
        for match in compiled.finditer(text):
            start, end = match.span()
            if start == end or not _range_free(occupied, start, end):
                continue
            groups = match.groupdict()
            tech = groups.get("tech") or match.group(0)
            label = groups.get("label")
            trans = [label] if label else []
            tokens.append(
                ProtectedToken(
                    kind="enricher",
                    start=start,
                    end=end,
                    raw=match.group(0),
                    tech_key=f"custom:{rule.name}:{tech}" if "tech" not in groups else tech,
                    translatable_parts=trans,
                )
            )
            _mark_occupied(occupied, start, end)
    return tokens


def _normalize_html_tag(match: re.Match[str]) -> tuple[str, list[str]]:
    closing = match.group(1) == "/"
    tag_name = match.group(2).lower()
    raw_attrs = match.group(3) or ""
    self_closing = match.group(4) == "/"
    if closing:
        return f"</{tag_name}>", []

    tech_attrs: list[str] = []
    trans_attrs: list[str] = []
    for attr_m in _ATTR_RE.finditer(raw_attrs):
        aname = attr_m.group(1).lower()
        aval = (
            attr_m.group(2)
            if attr_m.group(2) is not None
            else (attr_m.group(3) if attr_m.group(3) is not None else attr_m.group(4))
        )
        if aname in _TRANSLATABLE_HTML_ATTRS:
            if aval is not None:
                trans_attrs.append(aval)
            tech_attrs.append(aname)
        else:
            if aval is None:
                tech_attrs.append(aname)
            else:
                norm_val = _URL_IN_ATTR_RE.sub("<URL>", aval)
                tech_attrs.append(f"{aname}={norm_val}")

    attrs_sig = " ".join(sorted(tech_attrs))
    slash_suffix = "/" if self_closing else ""
    sig = f"<{tag_name}{' ' + attrs_sig if attrs_sig else ''}{slash_suffix}>"
    return sig, trans_attrs


def extract_protected_tokens(
    text: str | None,
    custom_enrichers: list[CustomEnricherRule] | None = None,
) -> list[ProtectedToken]:
    """Extract protected spans in fixed cascade order without double-counting nested labels."""
    if not text:
        return []

    length = len(text)
    occupied_stage12 = [False] * length
    occupied_all = [False] * length
    tokens: list[ProtectedToken] = []

    def _add_enricher_tokens(found: list[ProtectedToken]) -> None:
        tokens.extend(found)
        for tok in found:
            _mark_occupied(occupied_all, tok.start, tok.end)

    # 1. {{handlebars}}
    for m in _HANDLEBARS_RE.finditer(text):
        s, e = m.span()
        tokens.append(ProtectedToken(kind="handlebars", start=s, end=e, raw=m.group(0), tech_key=m.group(0)))
        _mark_occupied(occupied_stage12, s, e)
        _mark_occupied(occupied_all, s, e)

    # 2a. Enrichers conhecidos (core v14 + dnd5e + pf2e)
    _add_enricher_tokens(_scan_bracket_enrichers(text, occupied_stage12, known_only=True))
    _add_enricher_tokens(_scan_inline_rolls(text, occupied_stage12, known_only=True))

    # 2b. custom_enrichers do projeto
    if custom_enrichers:
        _add_enricher_tokens(_scan_custom_enrichers(text, occupied_stage12, custom_enrichers))

    # 2c. Heurística genérica (@Nome[...], &Nome[...], [[/nome ...]])
    _add_enricher_tokens(_scan_bracket_enrichers(text, occupied_stage12, known_only=False))
    _add_enricher_tokens(_scan_inline_rolls(text, occupied_stage12, known_only=False))

    # 3. URLs
    url_spans: list[tuple[int, int]] = []
    for m in _URL_RE.finditer(text):
        s, e = m.span()
        if not _range_free(occupied_all, s, e):
            continue
        raw_url = m.group(0).rstrip(".,;:!?")
        url_end = s + len(raw_url)
        if url_end <= s:
            continue
        tokens.append(ProtectedToken(kind="url", start=s, end=url_end, raw=raw_url, tech_key=raw_url))
        _mark_occupied(occupied_all, s, url_end)
        url_spans.append((s, url_end))

    # 4. Tags e entidades HTML/XML (não colidem com estágios 1-2 ou URLs fora de atributos)
    for m in _HTML_TAG_RE.finditer(text):
        s, e = m.span()
        if not _range_free(occupied_stage12, s, e):
            continue
        # Se alguma URL está contida estritamente dentro do atributo do <tag ...>, aceita ambos sem overlaps externos
        overlaps_external_url = any(
            not (s <= us and ue <= e) and not (ue <= s or us >= e)
            for us, ue in url_spans
        )
        if overlaps_external_url:
            continue
        sig, trans_attrs = _normalize_html_tag(m)
        tokens.append(
            ProtectedToken(
                kind="html",
                start=s,
                end=e,
                raw=m.group(0),
                tech_key=sig,
                translatable_parts=trans_attrs,
            )
        )
        _mark_occupied(occupied_all, s, e)

    for m in _HTML_ENTITY_RE.finditer(text):
        s, e = m.span()
        if not _range_free(occupied_all, s, e):
            continue
        tokens.append(ProtectedToken(kind="html", start=s, end=e, raw=m.group(0), tech_key=m.group(0)))
        _mark_occupied(occupied_all, s, e)

    # 5. Placeholders {nome} restantes
    for m in _PLACEHOLDER_RE.finditer(text):
        s, e = m.span()
        if not _range_free(occupied_all, s, e):
            continue
        tokens.append(
            ProtectedToken(
                kind="placeholder",
                start=s,
                end=e,
                raw=m.group(0),
                tech_key=m.group(1),
            )
        )
        _mark_occupied(occupied_all, s, e)

    tokens.sort(key=lambda t: (t.start, -(t.end - t.start)))
    return tokens


def _find_html_balance_errors(tokens: list[ProtectedToken]) -> list[str]:
    stack: list[str] = []
    broken: list[str] = []
    for tok in tokens:
        if tok.kind != "html" or not tok.raw.startswith("<"):
            continue
        m = _HTML_TAG_RE.match(tok.raw)
        if not m:
            continue
        is_close = m.group(1) == "/"
        tag_name = m.group(2).lower()
        is_self = m.group(4) == "/" or tag_name in _VOID_HTML_TAGS
        if is_close:
            if stack and stack[-1] == tag_name:
                stack.pop()
            else:
                broken.append(f"</{tag_name}>")
        elif not is_self:
            stack.append(tag_name)
    return broken + [f"<{tag}>" for tag in stack]


def inspect_base_defects(
    base_text: str | None,
    custom_enrichers: list[CustomEnricherRule] | None = None,
) -> list[ValidationIssue]:
    """Detect informational defects in the base source string (never blocks publishing)."""
    if not base_text:
        return []
    tokens = extract_protected_tokens(base_text, custom_enrichers=custom_enrichers)
    placeholder_names = {t.tech_key for t in tokens if t.kind == "placeholder"}
    enricher_labels = {
        part.strip()
        for t in tokens
        if t.kind == "enricher"
        for part in t.translatable_parts
        if part.strip()
    }
    collisions = sorted(placeholder_names & enricher_labels)
    if not collisions:
        return []
    return [
        ValidationIssue(
            rule_id="base_label_placeholder_collision",
            severity="info",
            message=(
                "Colisão informativa na base entre rótulo de enricher e placeholder: "
                + ", ".join(f"{{{c}}}" for c in collisions)
            ),
        )
    ]


def _missing_raw_tokens_by_kind(
    base_tokens: list[ProtectedToken],
    target_tokens: list[ProtectedToken],
    kind: TokenKind,
) -> list[str]:
    target_counts = Counter(t.tech_key for t in target_tokens if t.kind == kind)
    missing: list[str] = []
    seen_need = Counter(t.tech_key for t in base_tokens if t.kind == kind)
    for tech_key, base_cnt in seen_need.items():
        deficit = base_cnt - target_counts.get(tech_key, 0)
        if deficit > 0:
            sample = next((t.raw for t in base_tokens if t.kind == kind and t.tech_key == tech_key), tech_key)
            missing.extend(sample for _ in range(deficit))
    return missing


def missing_tokens_for_translation(
    base_text: str | None,
    target_text: str | None,
    custom_enrichers: list[CustomEnricherRule] | None = None,
) -> list[str]:
    """Return ordered raw tokens present in base that are missing from target translation."""
    if not base_text:
        return []
    base_tokens = extract_protected_tokens(base_text, custom_enrichers=custom_enrichers)
    if target_text is None:
        return []
    if not target_text:
        return [t.raw for t in base_tokens]
    target_tokens = extract_protected_tokens(target_text, custom_enrichers=custom_enrichers)
    missing: list[str] = []
    for kind in ("handlebars", "enricher", "url", "html", "placeholder"):
        missing.extend(_missing_raw_tokens_by_kind(base_tokens, target_tokens, kind))
    return missing


def _make_issue(
    rule_id: str,
    severity: IssueSeverity,
    message: str,
    missing_tokens: list[str],
    ctx: _IgnoreContext,
) -> ValidationIssue:
    ignored = ctx.find(rule_id)
    return ValidationIssue(
        rule_id=rule_id,
        severity=severity,
        message=message,
        missing_tokens=missing_tokens,
        is_ignored=ignored is not None,
        ignored_reason=ignored.reason if ignored is not None else "",
    )


def _validate_simple_kind(
    base_tokens: list[ProtectedToken],
    target_tokens: list[ProtectedToken],
    kind: TokenKind,
    rule_id: str,
    severity: IssueSeverity,
    message: str,
    ctx: _IgnoreContext,
) -> ValidationIssue | None:
    b_cnt = Counter(t.tech_key for t in base_tokens if t.kind == kind)
    t_cnt = Counter(t.tech_key for t in target_tokens if t.kind == kind)
    if b_cnt == t_cnt:
        return None
    missing = _missing_raw_tokens_by_kind(base_tokens, target_tokens, kind)
    return _make_issue(rule_id, severity, message, missing, ctx)


def validate_translation(
    key_path: str,
    lang: str,
    base_text: str | None,
    target_text: str | None,
    *,
    custom_enrichers: list[CustomEnricherRule] | None = None,
    ignored_warnings: list[IgnoredWarning] | None = None,
    ignore_empty: bool = True,
) -> list[ValidationIssue]:
    """Validate target translation against base tokens using cascade rules and ignored exceptions."""
    if not base_text or target_text is None:
        return []
    if ignore_empty and target_text == "":
        return []

    base_tokens = extract_protected_tokens(base_text, custom_enrichers=custom_enrichers)
    target_tokens = extract_protected_tokens(target_text, custom_enrichers=custom_enrichers)
    ctx = _IgnoreContext(
        ignored_warnings=ignored_warnings or [],
        key_path=key_path,
        lang=lang,
        value_hash=compute_value_hash(target_text),
    )
    issues: list[ValidationIssue] = []

    hb_issue = _validate_simple_kind(
        base_tokens,
        target_tokens,
        "handlebars",
        "handlebars_mismatch",
        "critical",
        "Expressão {{handlebars}} alterada ou ausente na tradução.",
        ctx,
    )
    if hb_issue is not None:
        issues.append(hb_issue)

    en_issue = _validate_simple_kind(
        base_tokens,
        target_tokens,
        "enricher",
        "enricher_tech_mismatch",
        "critical",
        "Parte técnica de enricher (@UUID/@Embed/@Check/[[...]]/customizado) alterada ou ausente.",
        ctx,
    )
    if en_issue is not None:
        issues.append(en_issue)

    b_ph = Counter(t.tech_key for t in base_tokens if t.kind == "placeholder")
    t_ph = Counter(t.tech_key for t in target_tokens if t.kind == "placeholder")
    if set(b_ph.keys()) != set(t_ph.keys()):
        missing_ph = [f"{{{k}}}" for k in sorted(set(b_ph.keys()) - set(t_ph.keys()))]
        extra_ph = [f"{{{k}}}" for k in sorted(set(t_ph.keys()) - set(b_ph.keys()))]
        parts: list[str] = []
        if missing_ph:
            parts.append(f"ausente(s): {', '.join(missing_ph)}")
        if extra_ph:
            parts.append(f"extra(s): {', '.join(extra_ph)}")
        issues.append(
            _make_issue(
                "placeholder_mismatch",
                "critical",
                f"Conjunto de placeholders divergente ({'; '.join(parts)}).",
                missing_ph,
                ctx,
            )
        )
    elif b_ph != t_ph:
        missing_rep = _missing_raw_tokens_by_kind(base_tokens, target_tokens, "placeholder")
        issues.append(
            _make_issue(
                "placeholder_count",
                "warning",
                "Contagem repetida de placeholders diverge da string base.",
                missing_rep,
                ctx,
            )
        )

    url_issue = _validate_simple_kind(
        base_tokens,
        target_tokens,
        "url",
        "url_mismatch",
        "warning",
        "URL omitida ou alterada em relação à string base.",
        ctx,
    )
    if url_issue is not None:
        issues.append(url_issue)

    b_html = Counter(t.tech_key for t in base_tokens if t.kind == "html")
    t_html = Counter(t.tech_key for t in target_tokens if t.kind == "html")
    extra_broken = Counter(_find_html_balance_errors(target_tokens)) - Counter(
        _find_html_balance_errors(base_tokens)
    )
    if b_html != t_html or bool(extra_broken):
        missing_html = _missing_raw_tokens_by_kind(base_tokens, target_tokens, "html")
        issues.append(
            _make_issue(
                "html_mismatch",
                "warning",
                "Tags/atributos ou entidades HTML/XML divergentes ou desbalanceadas.",
                missing_html,
                ctx,
            )
        )

    return issues
