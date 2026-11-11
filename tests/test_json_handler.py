import pytest

from app.core.json_handler import parse_lang_bytes


def test_parse_lang_bytes_extracts_style_spans_and_expanded_keys() -> None:
    raw = (
        b"\xef\xbb\xbf"
        b'{\r\n'
        b'  "ACTOR": {\r\n'
        b'    "Type": "Personagem",\r\n'
        b'    "Nested.Dotted": "Aninhado"\r\n'
        b'  },\r\n'
        b'  "UI.Save": "Salvar",\r\n'
        b'  "UI.Count": 42\r\n'
        b'}\r\n'
    )

    doc = parse_lang_bytes(raw)

    assert doc.fatal_error is None
    assert doc.style.has_bom is True
    assert doc.style.eol == "\r\n"
    assert doc.style.ends_with_newline is True
    assert doc.style.indent == "  "
    assert doc.style.all_non_ascii_escaped is False

    assert doc.entries["ACTOR.Type"].value == "Personagem"
    assert doc.entries["ACTOR.Nested.Dotted"].value == "Aninhado"
    assert doc.entries["UI.Save"].value == "Salvar"
    assert doc.entries["UI.Save"].is_string is True
    assert doc.entries["UI.Save"].line == 6

    # Span exato em BYTES UTF-8 diretamente sobre raw (incluindo BOM + acentos multi-byte)
    span = doc.entries["UI.Save"].value_span
    assert raw[span[0] : span[1]] == b'"Salvar"'
    assert doc.entries["ACTOR.Nested.Dotted"].value_span is not None
    actor_obj_span = doc.object_spans["ACTOR"]
    assert raw[actor_obj_span[0] : actor_obj_span[1]].startswith(b"{")
    assert raw[actor_obj_span[0] : actor_obj_span[1]].endswith(b"}")
    assert doc.entries["UI.Save"].column == 3

    # Folha não-string preservada como diagnóstico
    assert doc.entries["UI.Count"].is_string is False
    assert doc.entries["UI.Count"].value is None
    assert doc.entries["UI.Count"].raw_type == "int"


def test_parse_lang_bytes_detects_duplicates_overwrites_and_fatal_errors() -> None:
    # 1) Chaves duplicadas: mantém última ocorrência e lista linhas
    dup_raw = (
        b'{\n'
        b'  "T20.Immunity": "Primeira",\n'
        b'  "T20.Immunity": "Segunda"\n'
        b'}\n'
    )
    dup_doc = parse_lang_bytes(dup_raw)
    assert dup_doc.fatal_error is None
    assert dup_doc.entries["T20.Immunity"].value == "Segunda"
    assert dup_doc.entries["T20.Immunity"].line == 3
    assert len(dup_doc.duplicates) == 1
    assert dup_doc.duplicates[0].lines == (2, 3)

    # 2) Folha antes de ramo com mesmo prefixo -> erro fatal (Foundry descarta o arquivo)
    lbb_raw = b'{\n  "A": "folha",\n  "A.B": "ramo"\n}\n'
    lbb_doc = parse_lang_bytes(lbb_raw)
    assert lbb_doc.fatal_error is not None
    assert lbb_doc.fatal_error.kind == "leaf_before_branch"
    assert lbb_doc.fatal_error.line == 3
    assert "line 3" in lbb_doc.fatal_error.message

    # 3) Sobrescrita silenciosa (chave pontuada antes de objeto com mesmo prefixo)
    ov_raw = b'{\n  "A.C": "perdida",\n  "A": {\n    "B": "ok"\n  }\n}\n'
    ov_doc = parse_lang_bytes(ov_raw)
    assert ov_doc.fatal_error is None
    assert "A.C" not in ov_doc.entries
    assert ov_doc.entries["A.B"].value == "ok"
    assert len(ov_doc.overwrites) == 1
    assert ov_doc.overwrites[0].key_path == "A.C"

    # 4) JSON inválido -> fatal_error com número da linha
    bad_raw = b'{\n  "A": "ok",\n}\n'
    bad_doc = parse_lang_bytes(bad_raw)
    assert bad_doc.fatal_error is not None
    assert bad_doc.fatal_error.kind == "invalid_json"
    assert bad_doc.fatal_error.line == 3


def test_parse_lang_bytes_detects_all_non_ascii_escaped_and_tabs() -> None:
    esc_raw = b'{\n\t"A": "A\\u00e7\\u00e3o"\n}'
    esc_doc = parse_lang_bytes(esc_raw)
    assert esc_doc.style.indent == "\t"
    assert esc_doc.style.ends_with_newline is False
    assert esc_doc.style.all_non_ascii_escaped is True

    mixed_raw = '{\n  "A": "A\\u00e7\\u00e3o",\n  "B": "Mágica"\n}\n'.encode("utf-8")
    mixed_doc = parse_lang_bytes(mixed_raw)
    assert mixed_doc.style.all_non_ascii_escaped is False

