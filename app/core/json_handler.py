from __future__ import annotations

from bisect import bisect_right
import codecs
from dataclasses import dataclass, field
import json
import re
from typing import Any, Literal


_FORBIDDEN_SEGMENTS = frozenset({"__proto__", "constructor", "prototype"})
_NUMBER_RE = re.compile(r"-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?")
_WS = " \t\r\n"

DiagnosticKind = Literal[
    "invalid_json",
    "leaf_before_branch",
    "duplicate_key",
    "overwritten_key",
    "non_string",
]
InsertionMode = Literal["flat", "nested", "mixed"]


@dataclass(frozen=True)
class FileStyle:
    """Detected formatting metadata for lossless round-trip editing."""

    has_bom: bool = False
    eol: str = "\n"
    ends_with_newline: bool = True
    indent: str = "  "
    all_non_ascii_escaped: bool = False


@dataclass(frozen=True)
class DiagnosticIssue:
    """Structural or syntax issue detected while loading a localization file."""

    kind: DiagnosticKind
    key_path: str
    line: int
    message: str
    lines: tuple[int, ...] = ()


@dataclass(frozen=True)
class LangEntry:
    """Single flattened localization entry mapped to its UTF-8 byte spans."""

    key_path: str
    value: str | None
    is_string: bool
    raw_type: str
    line: int
    column: int
    key_span: tuple[int, int]
    value_span: tuple[int, int]
    source_file: str = ""


@dataclass
class ParsedLangDocument:
    """Result of parsing a Foundry localization JSON file from raw bytes."""

    style: FileStyle
    entries: dict[str, LangEntry] = field(default_factory=dict)
    ordered_keys: list[str] = field(default_factory=list)
    object_spans: dict[str, tuple[int, int]] = field(default_factory=dict)
    fatal_error: DiagnosticIssue | None = None
    duplicates: list[DiagnosticIssue] = field(default_factory=list)
    overwrites: list[DiagnosticIssue] = field(default_factory=list)
    non_string_keys: list[DiagnosticIssue] = field(default_factory=list)
    raw_bytes: bytes = b""
    _root_span: tuple[int, int] = (0, 0)
    _root_pairs: list[_RawPair] = field(default_factory=list, repr=False)


@dataclass
class _RawPair:
    raw_key: str
    key_span: tuple[int, int]
    value_span: tuple[int, int]
    line: int
    column: int
    is_object: bool
    children: list[_RawPair] | None = None
    scalar_value: Any = None
    raw_type: str = "str"


class _JsonSpanParser:
    """Strict RFC 8259 recursive-descent parser recording UTF-8 byte spans."""

    def __init__(self, text: str, bom_len: int) -> None:
        self.text = text
        self.n = len(text)
        self.pos = 0
        self.bom_len = bom_len
        self.line_starts = self._build_line_starts(text)
        self.byte_offsets = self._build_byte_offsets(text, bom_len)
        self.duplicates: list[tuple[str, tuple[int, ...]]] = []

    @staticmethod
    def _build_line_starts(text: str) -> list[int]:
        starts = [0]
        for idx, ch in enumerate(text):
            if ch == "\n":
                starts.append(idx + 1)
        return starts

    @staticmethod
    def _build_byte_offsets(text: str, bom_len: int) -> list[int]:
        offsets = [bom_len]
        total = bom_len
        for ch in text:
            total += len(ch.encode("utf-8"))
            offsets.append(total)
        return offsets

    def line_at(self, offset: int) -> int:
        return bisect_right(self.line_starts, offset)

    def col_at(self, offset: int) -> int:
        line_idx = self.line_at(offset) - 1
        return (offset - self.line_starts[line_idx]) + 1

    def byte_span(self, start_char: int, end_char: int) -> tuple[int, int]:
        return (self.byte_offsets[start_char], self.byte_offsets[end_char])

    def skip_ws(self) -> None:
        while self.pos < self.n and self.text[self.pos] in _WS:
            self.pos += 1

    def _scan_string(self, start: int) -> tuple[str, int]:
        pos = start + 1
        n = self.n
        text = self.text
        while pos < n:
            ch = text[pos]
            if ch == '"':
                end = pos + 1
                val = json.loads(text[start:end])
                if not isinstance(val, str):
                    raise ValueError(f"Expected string at line {self.line_at(start)}")
                return val, end
            if ch == "\\":
                pos += 2
                continue
            pos += 1
        raise ValueError(f"Unterminated string at line {self.line_at(start)}")

    def parse_root_object(self) -> tuple[tuple[int, int], list[_RawPair]]:
        self.skip_ws()
        if self.pos >= self.n or self.text[self.pos] != "{":
            raise ValueError(f"Expected '{{' at line {self.line_at(self.pos)}")
        root_start = self.pos
        pairs = self._parse_object(prefix=())
        root_end = self.pos
        self.skip_ws()
        if self.pos != self.n:
            raise ValueError(f"Unexpected trailing content at line {self.line_at(self.pos)}")
        return self.byte_span(root_start, root_end), pairs

    def _parse_object(self, prefix: tuple[str, ...]) -> list[_RawPair]:
        self.pos += 1  # consume '{'
        self.skip_ws()
        pairs: list[_RawPair] = []
        seen_lines: dict[str, list[int]] = {}

        if self.pos < self.n and self.text[self.pos] == "}":
            self.pos += 1
            return pairs

        while True:
            self.skip_ws()
            if self.pos >= self.n or self.text[self.pos] != '"':
                raise ValueError(f"Expected string key at line {self.line_at(self.pos)}")
            k_start = self.pos
            key_str, k_end = self._scan_string(k_start)
            self.pos = k_end
            line_no = self.line_at(k_start)
            col_no = self.col_at(k_start)

            self.skip_ws()
            if self.pos >= self.n or self.text[self.pos] != ":":
                raise ValueError(f"Expected ':' at line {self.line_at(self.pos)}")
            self.pos += 1
            self.skip_ws()

            v_start = self.pos
            pair = self._parse_value_into_pair(
                key_str=key_str,
                key_span=self.byte_span(k_start, k_end),
                v_start=v_start,
                line_no=line_no,
                col_no=col_no,
                prefix=prefix + (key_str,),
            )
            pairs.append(pair)
            seen_lines.setdefault(key_str, []).append(line_no)

            self.skip_ws()
            if self.pos >= self.n:
                raise ValueError(f"Unterminated object at line {self.line_at(self.pos)}")
            ch = self.text[self.pos]
            if ch == ",":
                self.pos += 1
                continue
            if ch == "}":
                self.pos += 1
                break
            raise ValueError(f"Expected ',' or '}}' at line {self.line_at(self.pos)}")

        for dup_key, lines in seen_lines.items():
            if len(lines) > 1:
                full = ".".join((*prefix, dup_key)) if prefix else dup_key
                self.duplicates.append((full, tuple(lines)))

        return pairs

    def _parse_value_into_pair(
        self,
        key_str: str,
        key_span: tuple[int, int],
        v_start: int,
        line_no: int,
        col_no: int,
        prefix: tuple[str, ...],
    ) -> _RawPair:
        if v_start >= self.n:
            raise ValueError(f"Unexpected end of file at line {self.line_at(v_start)}")
        if self.text[v_start] == "{":
            children = self._parse_object(prefix=prefix)
            return _RawPair(
                raw_key=key_str,
                key_span=key_span,
                value_span=self.byte_span(v_start, self.pos),
                line=line_no,
                column=col_no,
                is_object=True,
                children=children,
                raw_type="dict",
            )
        val, raw_type = self._parse_non_object_value()
        return _RawPair(
            raw_key=key_str,
            key_span=key_span,
            value_span=self.byte_span(v_start, self.pos),
            line=line_no,
            column=col_no,
            is_object=False,
            scalar_value=val,
            raw_type=raw_type,
        )

    def _parse_non_object_value(self) -> tuple[Any, str]:
        ch = self.text[self.pos]
        if ch == '"':
            s_val, end = self._scan_string(self.pos)
            self.pos = end
            return s_val, "str"
        if ch == "[":
            arr_val = self._parse_array()
            return arr_val, "list"
        if self.text.startswith("true", self.pos):
            self.pos += 4
            return True, "bool"
        if self.text.startswith("false", self.pos):
            self.pos += 5
            return False, "bool"
        if self.text.startswith("null", self.pos):
            self.pos += 4
            return None, "NoneType"
        m = _NUMBER_RE.match(self.text, self.pos)
        if m:
            num_str = m.group(0)
            self.pos = m.end()
            if "." in num_str or "e" in num_str or "E" in num_str:
                return float(num_str), "float"
            return int(num_str), "int"
        raise ValueError(f"Invalid JSON value at line {self.line_at(self.pos)}")

    def _parse_array(self) -> list[Any]:
        self.pos += 1  # consume '['
        self.skip_ws()
        items: list[Any] = []
        if self.pos < self.n and self.text[self.pos] == "]":
            self.pos += 1
            return items
        while True:
            self.skip_ws()
            if self.pos >= self.n:
                raise ValueError(f"Unterminated array at line {self.line_at(self.pos)}")
            if self.text[self.pos] == "{":
                items.append(self._parse_object(prefix=()))
            else:
                val, _ = self._parse_non_object_value()
                items.append(val)
            self.skip_ws()
            if self.pos >= self.n:
                raise ValueError(f"Unterminated array at line {self.line_at(self.pos)}")
            ch = self.text[self.pos]
            if ch == ",":
                self.pos += 1
                continue
            if ch == "]":
                self.pos += 1
                return items
            raise ValueError(f"Expected ',' or ']' at line {self.line_at(self.pos)}")


def _detect_style(raw_bytes: bytes, text: str, entries: dict[str, LangEntry]) -> FileStyle:
    has_bom = raw_bytes.startswith(codecs.BOM_UTF8)
    eol = "\r\n" if "\r\n" in text else "\n"
    ends_with_newline = text.endswith("\n")

    indent = "  "
    for line in text.splitlines():
        if line and line[0] in (" ", "\t"):
            stripped = line.lstrip(" \t")
            if stripped:
                indent = line[: len(line) - len(stripped)]
                break

    has_u_escape = False
    has_raw_non_ascii = False
    for entry in entries.values():
        if entry.is_string:
            raw_lit = raw_bytes[entry.value_span[0] : entry.value_span[1]].decode("utf-8")
            if re.search(r"\\u[0-9a-fA-F]{4}", raw_lit):
                has_u_escape = True
            if any(ord(c) > 127 for c in raw_lit):
                has_raw_non_ascii = True
    all_non_ascii_escaped = has_u_escape and not has_raw_non_ascii

    return FileStyle(
        has_bom=has_bom,
        eol=eol,
        ends_with_newline=ends_with_newline,
        indent=indent,
        all_non_ascii_escaped=all_non_ascii_escaped,
    )


def _ensure_branch(
    tree: dict[str, Any],
    ancestors: tuple[str, ...],
    full_path: str,
    line: int,
) -> tuple[dict[str, Any] | None, DiagnosticIssue | None]:
    curr = tree
    for depth, part in enumerate(ancestors):
        existing = curr.get(part)
        if existing is None:
            nxt: dict[str, Any] = {}
            curr[part] = nxt
            curr = nxt
        elif isinstance(existing, dict):
            curr = existing
        else:
            conflict_path = ".".join(ancestors[: depth + 1])
            return None, DiagnosticIssue(
                kind="leaf_before_branch",
                key_path=full_path,
                line=line,
                message=(
                    f"Leaf '{conflict_path}' defined before branch '{full_path}' "
                    f"at line {line} (Foundry discards file)."
                ),
            )
    return curr, None


def _expand_pairs(
    pairs: list[_RawPair],
    source_file: str,
    tree: dict[str, Any],
    object_spans: dict[str, tuple[int, int]],
    overwrites: list[DiagnosticIssue],
    prefix: tuple[str, ...] = (),
) -> DiagnosticIssue | None:
    """Mirror Foundry's expandObject semantics, detecting fatal leaf-before-branch collisions."""
    for pair in pairs:
        segments = tuple(pair.raw_key.split("."))
        if any(seg in _FORBIDDEN_SEGMENTS for seg in segments):
            continue
        path_parts = prefix + segments
        full_path = ".".join(path_parts)
        curr, err = _ensure_branch(tree, path_parts[:-1], full_path, pair.line)
        if err is not None:
            return err
        assert curr is not None

        last = path_parts[-1]
        existing_last = curr.get(last)

        if pair.is_object:
            if existing_last is not None and not isinstance(existing_last, dict):
                return DiagnosticIssue(
                    kind="leaf_before_branch",
                    key_path=full_path,
                    line=pair.line,
                    message=(
                        f"Leaf '{full_path}' defined before branch at line {pair.line} "
                        "(Foundry discards file)."
                    ),
                )
            if isinstance(existing_last, dict):
                for sub_key in list(existing_last.keys()):
                    overwrites.append(
                        DiagnosticIssue(
                            kind="overwritten_key",
                            key_path=f"{full_path}.{sub_key}",
                            line=pair.line,
                            message=(
                                f"Branch at line {pair.line} overwrites earlier "
                                f"'{full_path}.{sub_key}'."
                            ),
                        )
                    )
            sub_tree: dict[str, Any] = {}
            curr[last] = sub_tree
            object_spans[full_path] = pair.value_span
            assert pair.children is not None
            err = _expand_pairs(
                pair.children,
                source_file,
                sub_tree,
                object_spans,
                overwrites,
                prefix=path_parts,
            )
            if err is not None:
                return err
        else:
            if isinstance(existing_last, dict):
                overwrites.append(
                    DiagnosticIssue(
                        kind="overwritten_key",
                        key_path=full_path,
                        line=pair.line,
                        message=f"Leaf '{full_path}' at line {pair.line} overwrites earlier branch.",
                    )
                )
            is_str = pair.raw_type == "str"
            curr[last] = LangEntry(
                key_path=full_path,
                value=pair.scalar_value if is_str else None,
                is_string=is_str,
                raw_type=pair.raw_type,
                line=pair.line,
                column=pair.column,
                key_span=pair.key_span,
                value_span=pair.value_span,
                source_file=source_file,
            )
    return None


def _collect_entries(tree: dict[str, Any], out: dict[str, LangEntry], order: list[str]) -> None:
    for val in tree.values():
        if isinstance(val, LangEntry):
            out[val.key_path] = val
            order.append(val.key_path)
        elif isinstance(val, dict):
            _collect_entries(val, out, order)


def parse_lang_bytes(raw_bytes: bytes, source_file: str = "") -> ParsedLangDocument:
    """Parse raw UTF-8 (with optional BOM) JSON bytes into entries, UTF-8 byte spans, style, and diagnostics."""
    has_bom = raw_bytes.startswith(codecs.BOM_UTF8)
    bom_len = len(codecs.BOM_UTF8) if has_bom else 0
    try:
        text = raw_bytes.decode("utf-8-sig" if has_bom else "utf-8")
    except UnicodeDecodeError as exc:
        style = FileStyle(has_bom=has_bom)
        return ParsedLangDocument(
            style=style,
            fatal_error=DiagnosticIssue(
                kind="invalid_json",
                key_path="",
                line=1,
                message=f"UTF-8 decode error: {exc}",
            ),
            raw_bytes=raw_bytes,
        )

    parser = _JsonSpanParser(text, bom_len=bom_len)
    try:
        root_span, pairs = parser.parse_root_object()
    except (ValueError, json.JSONDecodeError) as exc:
        style = _detect_style(raw_bytes, text, {})
        return ParsedLangDocument(
            style=style,
            fatal_error=DiagnosticIssue(
                kind="invalid_json",
                key_path="",
                line=parser.line_at(min(parser.pos, len(text))),
                message=str(exc),
            ),
            raw_bytes=raw_bytes,
        )

    tree: dict[str, Any] = {}
    object_spans: dict[str, tuple[int, int]] = {"": root_span}
    overwrites: list[DiagnosticIssue] = []
    fatal = _expand_pairs(pairs, source_file, tree, object_spans, overwrites)
    if fatal is not None:
        style = _detect_style(raw_bytes, text, {})
        return ParsedLangDocument(
            style=style,
            fatal_error=fatal,
            raw_bytes=raw_bytes,
        )

    entries: dict[str, LangEntry] = {}
    ordered_keys: list[str] = []
    _collect_entries(tree, entries, ordered_keys)

    duplicates = [
        DiagnosticIssue(
            kind="duplicate_key",
            key_path=dup_key,
            line=lines[-1],
            lines=lines,
            message=f"Duplicate key '{dup_key}' on lines {', '.join(map(str, lines))}.",
        )
        for dup_key, lines in parser.duplicates
    ]
    non_string_keys = [
        DiagnosticIssue(
            kind="non_string",
            key_path=e.key_path,
            line=e.line,
            message=f"Non-string value ({e.raw_type}) at '{e.key_path}' on line {e.line}.",
        )
        for e in entries.values()
        if not e.is_string
    ]
    style = _detect_style(raw_bytes, text, entries)
    return ParsedLangDocument(
        style=style,
        entries=entries,
        ordered_keys=ordered_keys,
        object_spans=object_spans,
        duplicates=duplicates,
        overwrites=overwrites,
        non_string_keys=non_string_keys,
        raw_bytes=raw_bytes,
        _root_span=root_span,
        _root_pairs=pairs,
    )


def _reject_non_rfc_constant(token: str) -> Any:
    raise ValueError(f"Non-standard JSON constant '{token}' is not allowed.")


def _find_object_node(
    pairs: list[_RawPair],
    root_span: tuple[int, int],
    target_path: tuple[str, ...],
) -> tuple[tuple[int, int], list[_RawPair]] | None:
    if not target_path:
        return root_span, pairs
    curr_pairs = pairs
    curr_span = root_span
    idx = 0
    while idx < len(target_path):
        matched = False
        for pair in reversed(curr_pairs):
            if not pair.is_object:
                continue
            segs = tuple(pair.raw_key.split("."))
            end_idx = idx + len(segs)
            if end_idx <= len(target_path) and target_path[idx:end_idx] == segs:
                curr_span = pair.value_span
                curr_pairs = pair.children or []
                idx = end_idx
                matched = True
                break
        if not matched:
            return None
    return curr_span, curr_pairs


def _collect_pair_paths(
    pairs: list[_RawPair],
    prefix: tuple[str, ...],
    out_leaves: dict[str, tuple[list[_RawPair], _RawPair]],
    out_parents: dict[int, tuple[list[_RawPair], _RawPair]],
) -> None:
    for pair in pairs:
        segs = tuple(pair.raw_key.split("."))
        if any(seg in _FORBIDDEN_SEGMENTS for seg in segs):
            continue
        full_parts = prefix + segs
        if pair.is_object:
            assert pair.children is not None
            for child in pair.children:
                out_parents[id(child)] = (pairs, pair)
            _collect_pair_paths(pair.children, full_parts, out_leaves, out_parents)
        else:
            out_leaves[".".join(full_parts)] = (pairs, pair)


def _collect_deletion_cuts(
    pairs: list[_RawPair],
    obj_span: tuple[int, int],
    removed_ids: set[int],
    cuts: list[tuple[int, int, bytes]],
) -> None:
    if not pairs:
        return
    if all(id(p) in removed_ids for p in pairs):
        cuts.append((obj_span[0] + 1, obj_span[1] - 1, b""))
        return

    surviving_indices = [i for i, p in enumerate(pairs) if id(p) not in removed_ids]
    last_surviving_idx = surviving_indices[-1]

    idx = 0
    while idx < len(pairs):
        pair = pairs[idx]
        if id(pair) not in removed_ids:
            if pair.is_object and pair.children is not None:
                _collect_deletion_cuts(pair.children, pair.value_span, removed_ids, cuts)
            idx += 1
            continue

        if idx < last_surviving_idx:
            # Remove run of removed items before the next surviving item
            end_idx = idx
            while end_idx + 1 < last_surviving_idx and id(pairs[end_idx + 1]) in removed_ids:
                end_idx += 1
            next_surviving = pairs[end_idx + 1]
            cuts.append((pair.key_span[0], next_surviving.key_span[0], b""))
            idx = end_idx + 1
        else:
            # Trailing removed items after last_surviving_idx
            prev_pair = pairs[last_surviving_idx]
            cuts.append((prev_pair.value_span[1], pairs[-1].value_span[1], b""))
            break


def _apply_byte_replacements(raw_bytes: bytes, replacements: list[tuple[int, int, bytes]]) -> bytes:
    if not replacements:
        return raw_bytes
    ordered = sorted(replacements, key=lambda item: (item[0], item[1]), reverse=True)
    buf = bytearray(raw_bytes)
    for start, end, new_bytes in ordered:
        buf[start:end] = new_bytes
    return bytes(buf)


def _format_nested_value(
    parts: tuple[str, ...],
    value: str,
    style: FileStyle,
    depth: int,
) -> str:
    val_lit = json.dumps(value, ensure_ascii=style.all_non_ascii_escaped)
    key_lit = json.dumps(parts[0], ensure_ascii=style.all_non_ascii_escaped)
    if len(parts) == 1:
        return f"{key_lit}: {val_lit}"
    inner_indent = style.indent * (depth + 1)
    closing_indent = style.indent * depth
    inner_pair = _format_nested_value(parts[1:], value, style, depth + 1)
    return f"{key_lit}: {{{style.eol}{inner_indent}{inner_pair}{style.eol}{closing_indent}}}"


def _detect_insertion_mode(doc: ParsedLangDocument) -> InsertionMode:
    has_nested = any(pair.is_object for pair in doc._root_pairs)
    has_dotted_root = any((not pair.is_object) and ("." in pair.raw_key) for pair in doc._root_pairs)
    if not has_nested and has_dotted_root:
        return "flat"
    if has_nested and has_dotted_root:
        return "mixed"
    return "nested"


def _splice_pair_insertion(
    current_bytes: bytes,
    pair_bytes: bytes,
    style: FileStyle,
    indent_str: str,
    is_inline_obj: bool,
    pos: int,
    before: bool = False,
) -> bytes:
    if is_inline_obj:
        ins = (pair_bytes + b", ") if before else (b", " + pair_bytes)
    else:
        sep = (f",{style.eol}{indent_str}").encode("utf-8")
        ins = (pair_bytes + sep) if before else (sep + pair_bytes)
    return current_bytes[:pos] + ins + current_bytes[pos:]


def _deepest_existing_object(
    doc: ParsedLangDocument,
    parts: tuple[str, ...],
) -> tuple[tuple[str, ...], tuple[int, int], list[_RawPair]]:
    for depth in range(len(parts) - 1, 0, -1):
        prefix = parts[:depth]
        found = _find_object_node(doc._root_pairs, doc._root_span, prefix)
        if found is not None:
            return prefix, found[0], found[1]
    return (), doc._root_span, doc._root_pairs


def _pair_order_bounds(
    pair: _RawPair,
    parent_prefix: tuple[str, ...],
    base_rank: dict[str, int],
) -> int | None:
    prefix_str = ".".join((*parent_prefix, pair.raw_key)) if parent_prefix else pair.raw_key
    if not pair.is_object:
        return base_rank.get(prefix_str)
    sub_prefix = f"{prefix_str}."
    ranks = [rank for k, rank in base_rank.items() if k.startswith(sub_prefix)]
    return min(ranks) if ranks else None


def _insert_one_key(
    current_bytes: bytes,
    key_path: str,
    value: str,
    base_rank: dict[str, int],
    fallback_style: FileStyle | None,
) -> bytes:
    doc = parse_lang_bytes(current_bytes)
    if doc.fatal_error is not None:
        raise ValueError(f"Cannot insert '{key_path}' into invalid JSON: {doc.fatal_error.message}")

    style = doc.style
    if not doc._root_pairs and fallback_style is not None:
        style = fallback_style

    mode = _detect_insertion_mode(doc)
    parts = tuple(key_path.split("."))
    parent_prefix, obj_span, siblings = _deepest_existing_object(doc, parts)

    target_rank = base_rank.get(key_path)
    after_pair: _RawPair | None = None
    before_pair: _RawPair | None = None

    def _find_neighbors(cands: list[_RawPair], p_prefix: tuple[str, ...]) -> tuple[_RawPair | None, _RawPair | None]:
        aft: _RawPair | None = None
        bef: _RawPair | None = None
        if target_rank is not None:
            for sib in cands:
                sib_rank = _pair_order_bounds(sib, p_prefix, base_rank)
                if sib_rank is not None:
                    if sib_rank < target_rank:
                        aft = sib
                    elif sib_rank > target_rank and bef is None:
                        bef = sib
        return aft, bef

    rel_parts: tuple[str, ...]
    if mode == "flat":
        parent_prefix = ()
        obj_span = doc._root_span
        siblings = doc._root_pairs
        rel_parts = (key_path,)
        after_pair, before_pair = _find_neighbors(siblings, parent_prefix)
    elif mode == "mixed" and not parent_prefix:
        after_pair, before_pair = _find_neighbors(siblings, ())
        neighbor = after_pair or before_pair
        if neighbor is not None and neighbor.is_object:
            rel_parts = parts
        else:
            rel_parts = (key_path,)
    else:
        rel_parts = parts[len(parent_prefix) :]
        after_pair, before_pair = _find_neighbors(siblings, parent_prefix)

    depth = len(parent_prefix) + 1
    indent_str = style.indent * depth
    parent_indent = style.indent * (depth - 1)
    is_inline_obj = b"\n" not in current_bytes[obj_span[0] : obj_span[1]] and len(siblings) > 0

    pair_text = _format_nested_value(rel_parts, value, style, depth=depth)
    pair_bytes = pair_text.encode("utf-8")

    if not siblings:
        body = f"{style.eol}{indent_str}{pair_text}{style.eol}{parent_indent}".encode("utf-8")
        return current_bytes[: obj_span[0] + 1] + body + current_bytes[obj_span[1] - 1 :]

    if after_pair is not None:
        return _splice_pair_insertion(
            current_bytes, pair_bytes, style, indent_str, is_inline_obj, after_pair.value_span[1], before=False
        )
    if before_pair is not None:
        return _splice_pair_insertion(
            current_bytes, pair_bytes, style, indent_str, is_inline_obj, before_pair.key_span[0], before=True
        )
    return _splice_pair_insertion(
        current_bytes, pair_bytes, style, indent_str, is_inline_obj, siblings[-1].value_span[1], before=False
    )


def validate_written_payload(
    original_doc: ParsedLangDocument,
    candidate_bytes: bytes,
    edits: dict[str, str],
    deletions: set[str],
) -> None:
    """Strictly validate JSON syntax, Foundry expandObject safety, and diff integrity in memory."""
    has_bom = candidate_bytes.startswith(codecs.BOM_UTF8)
    text = candidate_bytes.decode("utf-8-sig" if has_bom else "utf-8")
    json.loads(text, parse_constant=_reject_non_rfc_constant)

    reparsed = parse_lang_bytes(candidate_bytes)
    if reparsed.fatal_error is not None:
        raise ValueError(f"Generated payload failed Foundry expandObject check: {reparsed.fatal_error.message}")
    if len(reparsed.overwrites) > len(original_doc.overwrites):
        raise ValueError("Generated payload introduced unexpected expandObject key overwrites.")

    for key, expected_val in edits.items():
        entry = reparsed.entries.get(key)
        if entry is None or not entry.is_string or entry.value != expected_val:
            raise ValueError(f"Payload verification failed for edited key '{key}'.")
    for key in deletions:
        if key in reparsed.entries:
            raise ValueError(f"Payload verification failed: deleted key '{key}' still present.")


def apply_surgical_edits(
    raw_bytes: bytes,
    edits: dict[str, str],
    deletions: set[str],
    base_order: list[str],
    fallback_style: FileStyle | None = None,
) -> bytes:
    """Apply value edits, deletions (pruning empty parents), and relative insertions preserving style."""
    orig_doc = parse_lang_bytes(raw_bytes)
    if orig_doc.fatal_error is not None:
        raise ValueError(f"Cannot edit malformed JSON file: {orig_doc.fatal_error.message}")

    replacements: list[tuple[int, int, bytes]] = []
    inserts: dict[str, str] = {}

    for key, new_val in edits.items():
        if key in deletions:
            continue
        existing = orig_doc.entries.get(key)
        if existing is not None:
            if not existing.is_string:
                raise ValueError(f"Cannot overwrite non-string key '{key}'.")
            if existing.value != new_val:
                lit = json.dumps(new_val, ensure_ascii=orig_doc.style.all_non_ascii_escaped).encode("utf-8")
                replacements.append((existing.value_span[0], existing.value_span[1], lit))
        else:
            inserts[key] = new_val

    effective_deletions = {k for k in deletions if k in orig_doc.entries}
    if not replacements and not effective_deletions and not inserts:
        return raw_bytes

    if effective_deletions:
        leaf_map: dict[str, tuple[list[_RawPair], _RawPair]] = {}
        parent_map: dict[int, tuple[list[_RawPair], _RawPair]] = {}
        _collect_pair_paths(orig_doc._root_pairs, (), leaf_map, parent_map)
        removed_ids: set[int] = set()
        for key in effective_deletions:
            pair_info = leaf_map.get(key)
            if pair_info is None:
                continue
            siblings, node = pair_info
            removed_ids.add(id(node))
            curr_siblings = siblings
            curr_node = node
            while all(id(s) in removed_ids for s in curr_siblings):
                parent_info = parent_map.get(id(curr_node))
                if parent_info is None:
                    break
                curr_siblings, curr_node = parent_info
                removed_ids.add(id(curr_node))

        _collect_deletion_cuts(orig_doc._root_pairs, orig_doc._root_span, removed_ids, replacements)

    result_bytes = _apply_byte_replacements(raw_bytes, replacements)

    if inserts:
        base_rank = {k: i for i, k in enumerate(base_order)}
        ordered_inserts = [k for k in base_order if k in inserts] + [
            k for k in inserts if k not in base_rank
        ]
        for key in ordered_inserts:
            result_bytes = _insert_one_key(
                result_bytes,
                key_path=key,
                value=inserts[key],
                base_rank=base_rank,
                fallback_style=fallback_style,
            )

    validate_written_payload(orig_doc, result_bytes, edits, effective_deletions)
    return result_bytes
