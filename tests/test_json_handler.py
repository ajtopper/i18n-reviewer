import pytest

from app.core.json_handler import apply_surgical_edits, parse_lang_bytes


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


def test_surgical_round_trip_no_changes_and_value_edit_on_non_canonical_and_duplicates() -> None:
    non_canon = (
        b"\xef\xbb\xbf"
        b'{\r\n'
        b'"A" : "A\\u00e7\\u00e3o",\r\n'
        b'\r\n'
        b'  "DUP": "Primeira",\r\n'
        b'  "DUP": "Segunda",\r\n'
        b'  "INLINE": {"X": "1", "Y": "2"}\r\n'
        b'}'
    )
    # 1) Nada mudou -> bytes idênticos
    assert apply_surgical_edits(non_canon, edits={}, deletions=set(), base_order=[]) == non_canon

    # 2) Editar apenas DUP -> mantém BOM, CRLF, "A" : "\u00e7...", linha em branco, sem newline final e 1ª DUP
    edited = apply_surgical_edits(
        non_canon,
        edits={"DUP": "Segunda editada", "INLINE.Y": "Dois"},
        deletions=set(),
        base_order=["A", "DUP", "INLINE.X", "INLINE.Y"],
    )
    text = edited.decode("utf-8-sig")
    assert edited.startswith(b"\xef\xbb\xbf")
    assert not edited.endswith(b"\n")
    assert '"A" : "A\\u00e7\\u00e3o"' in text
    assert '\r\n\r\n  "DUP": "Primeira",\r\n  "DUP": "Segunda editada",' in text
    assert '"INLINE": {"X": "1", "Y": "Dois"}' in text

    # 3) Arquivo 100% \uXXXX grava novo valor também escapado
    all_esc = b'{\n  "A": "A\\u00e7\\u00e3o"\n}\n'
    edited_esc = apply_surgical_edits(all_esc, edits={"A": "Poção"}, deletions=set(), base_order=["A"])
    assert b'"A": "Po\\u00e7\\u00e3o"' in edited_esc


def test_surgical_insertion_relative_order_in_flat_nested_and_mixed_and_orphan_pruning() -> None:
    base_order = ["APP.First", "APP.Middle", "APP.Last", "NEW.Deep.Key", "KEEP"]

    # 1) Destino plano
    flat_raw = b'{\n  "APP.First": "Primeiro",\n  "APP.Last": "Ultimo",\n  "ORPHAN": "Lixo",\n  "KEEP": "Manter"\n}\n'
    flat_out = apply_surgical_edits(
        flat_raw,
        edits={"APP.Middle": "Meio", "NEW.Deep.Key": "Novo"},
        deletions={"ORPHAN"},
        base_order=base_order,
    ).decode("utf-8")
    assert flat_out.index('"APP.First"') < flat_out.index('"APP.Middle"') < flat_out.index('"APP.Last"')
    assert '"NEW.Deep.Key": "Novo"' in flat_out
    assert "ORPHAN" not in flat_out
    assert parse_lang_bytes(flat_out.encode("utf-8")).entries["APP.Middle"].value == "Meio"

    # 2) Destino aninhado + poda de objeto pai vazio ao remover órfã
    nested_raw = (
        b'{\r\n'
        b'  "APP": {\r\n'
        b'    "First": "Primeiro",\r\n'
        b'    "Last": "Ultimo"\r\n'
        b'  },\r\n'
        b'  "DEAD": {\r\n'
        b'    "Branch": {\r\n'
        b'      "Leaf": "Remover"\r\n'
        b'    }\r\n'
        b'  },\r\n'
        b'  "KEEP": "Manter"\r\n'
        b'}\r\n'
    )
    nested_out = apply_surgical_edits(
        nested_raw,
        edits={"APP.Middle": "Meio", "NEW.Deep.Key": "Profundo"},
        deletions={"DEAD.Branch.Leaf"},
        base_order=base_order,
    ).decode("utf-8")
    assert "\r\n" in nested_out
    assert '"DEAD"' not in nested_out
    assert nested_out.index('"First"') < nested_out.index('"Middle"') < nested_out.index('"Last"')
    parsed_nested = parse_lang_bytes(nested_out.encode("utf-8"))
    assert parsed_nested.entries["NEW.Deep.Key"].value == "Profundo"
    assert parsed_nested.entries["KEEP"].value == "Manter"

    # 3) Destino misto (objeto existente INLINE + nova chave plana e vizinho aninhado)
    mixed_raw = (
        b'{\n'
        b'  "APP.First": "Primeiro",\n'
        b'  "MOD": {\n'
        b'    "Alpha": "Alfa"\n'
        b'  },\n'
        b'  "INLINE": {"A": "Alfa"}\n'
        b'}\n'
    )
    mixed_out = apply_surgical_edits(
        mixed_raw,
        edits={
            "INLINE.B": "Beta",
            "APP.Mid": "Meio",
            "MOD.Beta": "BetaMod",
            "NEWOBJ.Sub.Item": "NovoItem",
        },
        deletions=set(),
        base_order=["APP.First", "APP.Mid", "MOD.Alpha", "MOD.Beta", "NEWOBJ.Sub.Item", "INLINE.A", "INLINE.B"],
    ).decode("utf-8")
    parsed_mixed = parse_lang_bytes(mixed_out.encode("utf-8"))
    assert parsed_mixed.entries["INLINE.B"].value == "Beta"
    assert parsed_mixed.entries["APP.Mid"].value == "Meio"
    assert parsed_mixed.entries["MOD.Beta"].value == "BetaMod"
    assert parsed_mixed.entries["NEWOBJ.Sub.Item"].value == "NovoItem"
    # Vizinho MOD é aninhado -> NEWOBJ após MOD.Beta também entra aninhado!
    assert '"APP.Mid": "Meio"' in mixed_out
    assert '"NEWOBJ": {' in mixed_out



