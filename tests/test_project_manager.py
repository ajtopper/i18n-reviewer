import json
from pathlib import Path

from app.core.project_manager import (
    CellKind,
    discover_manifest,
    load_package_session,
)


def _write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def test_discover_manifest_handles_base_http_escape_case_conditionals_and_babele(
    tmp_path: Path,
) -> None:
    pkg = tmp_path / "my-mod"
    _write_json(
        pkg / "module.json",
        {
            "id": "my-mod",
            "languages": [
                {"lang": "pt-br", "name": "Português", "path": "lang/pt-br.json"},
                {"lang": "en", "name": "English", "path": "lang/en.json"},
                {"lang": "es", "name": "Español", "path": "lang/es.json", "system": "dnd5e"},
                {"lang": "fr", "name": "Remote", "path": "https://example.com/fr.json"},
                {"lang": "de", "name": "Bad", "path": "../outside.json"},
            ],
        },
    )
    _write_json(pkg / "lang/en.json", {"A": "One"})
    _write_json(pkg / "lang/pt-br.json", {"A": "Um"})
    _write_json(pkg / "lang/es.json", {"A": "Uno"})
    # Arquivo do Babele fora de languages[] deve ser ignorado
    _write_json(pkg / "lang/pt-br/compendium/dnd5e.spells.json", {"Fireball": "Bola de Fogo"})

    info = discover_manifest(pkg / "module.json")

    assert info.manifest_type == "module"
    assert info.package_id == "my-mod"
    assert info.default_base_lang == "en"

    by_lang = {entry.lang: entry for entry in info.entries}
    assert by_lang["en"].editable is True
    assert by_lang["pt-br"].editable is True
    assert by_lang["es"].conditional == "system: dnd5e"
    assert by_lang["fr"].is_http is True
    assert by_lang["fr"].editable is False
    assert by_lang["de"].editable is False

    kinds = {w.kind for w in info.warnings}
    assert "non_canonical_bcp47" in kinds
    assert "remote_http" in kinds
    assert "path_escape" in kinds
    assert all("compendium" not in e.path for e in info.entries)


def test_load_package_session_unifies_multifile_cldr_plurals_and_cell_kinds(
    tmp_path: Path,
) -> None:
    pkg = tmp_path / "sys-mod"
    _write_json(
        pkg / "system.json",
        {
            "id": "sys-mod",
            "languages": [
                {"lang": "en", "name": "English Main", "path": "lang/en.json"},
                {"lang": "en", "name": "English Extra", "path": "lang/extra-en.json"},
                {"lang": "pt-BR", "name": "PT1", "path": "lang/pt1.json"},
                {"lang": "pt-BR", "name": "PT2", "path": "lang/pt2.json"},
                {"lang": "es", "name": "ES", "path": "lang/es.json"},
            ],
        },
    )
    _write_json(
        pkg / "lang/en.json",
        {
            "UI": {"Title": "Title", "Empty": "Empty", "Same": "OK", "Count": "Count"},
            "Points": {"one": "{n} pt", "other": "{n} pts"},
            "Other": {"one": "{n} item", "other": "{n} items"},
            "Conflict": {"Sub": "Leaf in base"},
        },
    )
    _write_json(pkg / "lang/extra-en.json", {"EXTRA": {"Note": "Extra note"}})
    _write_json(
        pkg / "lang/pt1.json",
        {
            "UI": {"Title": "Título antigo", "Empty": "", "Same": "OK", "Count": 10},
            "Points": {"one": "{n} pt", "many": "{n} pontos", "other": "{n} pontos"},
            "Other": {"one": "{n} item", "other": "{n} itens"},
            "Conflict": "String no destino",
            "ORPHAN": {"Legacy": "Antiga"},
        },
    )
    _write_json(
        pkg / "lang/pt2.json",
        {
            "UI": {"Title": "Título novo"},
        },
    )
    _write_json(pkg / "lang/es.json", {"UI": {"Title": "Título"}})

    # Desabilita 'es' opcionalmente para validar filtro de entradas na carga
    info = discover_manifest(pkg / "system.json")
    enabled = [e for e in info.entries if e.lang != "es"]
    session = load_package_session(info, base_lang="en", selected_entries=enabled)

    assert session.target_langs == ["pt-BR"]
    rows = {r.key_path: r for r in session.rows}

    # Multi-arquivo: último vence em colisão e registra colisão
    assert rows["UI.Title"].cells["pt-BR"].prod_value == "Título novo"
    assert rows["UI.Title"].cells["pt-BR"].source_file == "lang/pt2.json"
    assert any(w.kind == "multi_file_collision" and w.key_path == "UI.Title" for w in session.warnings)

    # Diferenciação de estados
    assert rows["EXTRA.Note"].cells["pt-BR"].kind == CellKind.MISSING
    assert rows["UI.Empty"].cells["pt-BR"].kind == CellKind.EMPTY
    assert rows["UI.Same"].cells["pt-BR"].kind == CellKind.SAME_AS_BASE
    assert rows["UI.Count"].cells["pt-BR"].kind == CellKind.NON_STRING
    assert rows["ORPHAN.Legacy"].cells["pt-BR"].kind == CellKind.ORPHAN

    # Conflito estrutural (objeto na base vs string no destino)
    assert rows["Conflict.Sub"].cells["pt-BR"].kind == CellKind.STRUCTURAL_CONFLICT
    assert rows["Conflict"].cells["pt-BR"].kind == CellKind.STRUCTURAL_CONFLICT

    # Plurais CLDR: pt-BR tem .many válido (NÃO é órfã), e sugere Other.many ausente
    assert rows["Points.many"].cells["pt-BR"].kind == CellKind.TRANSLATED
    assert rows["Other.many"].cells["pt-BR"].kind == CellKind.MISSING
    assert rows["Other.many"].base_text == "{n} items"


def test_load_package_session_supports_external_base_and_isolates_fatal_file(
    tmp_path: Path,
) -> None:
    pkg = tmp_path / "pt-only-mod"
    _write_json(
        pkg / "module.json",
        {
            "id": "pt-only-mod",
            "languages": [
                {"lang": "pt-BR", "path": "lang/pt-BR.json"},
                {"lang": "es", "path": "lang/es.json"},
            ],
        },
    )
    _write_json(pkg / "lang/pt-BR.json", {"HELLO": "Olá"})
    # es.json tem folha antes de ramo (fatal para o Foundry)
    (pkg / "lang/es.json").write_text('{"HELLO": "Hola", "HELLO.Sub": "Bad"}\n', encoding="utf-8")

    ext_en = tmp_path / "external-en.json"
    _write_json(ext_en, {"HELLO": "Hello", "BYE": "Bye"})

    info = discover_manifest(pkg / "module.json")
    session = load_package_session(info, base_lang="en", base_external_path=ext_en)

    assert session.base_lang == "en"
    assert session.target_langs == ["pt-BR", "es"]
    rows = {r.key_path: r for r in session.rows}
    assert rows["HELLO"].cells["pt-BR"].kind == CellKind.TRANSLATED
    assert rows["BYE"].cells["pt-BR"].kind == CellKind.MISSING
    assert rows["HELLO"].cells["es"].readonly is True
    assert any(w.kind == "fatal_file" and w.lang == "es" for w in session.warnings)


def test_cldr_plurals_are_isolated_per_target_language(tmp_path: Path) -> None:
    pkg = tmp_path / "cldr-mod"
    _write_json(
        pkg / "module.json",
        {
            "id": "cldr-mod",
            "languages": [
                {"lang": "en", "path": "lang/en.json"},
                {"lang": "pt-BR", "path": "lang/pt-BR.json"},
                {"lang": "de", "path": "lang/de.json"},
            ],
        },
    )
    _write_json(pkg / "lang/en.json", {"Pts": {"one": "{n} pt", "other": "{n} pts"}})
    _write_json(pkg / "lang/pt-BR.json", {"Pts": {"one": "{n} ponto", "other": "{n} pontos"}})
    _write_json(
        pkg / "lang/de.json",
        {"Pts": {"one": "{n} Pkt", "many": "Espúrio em de", "other": "{n} Pkte"}},
    )

    info = discover_manifest(pkg / "module.json")
    session = load_package_session(info)
    rows = {r.key_path: r for r in session.rows}

    # .many é sugerido como MISSING para pt-BR, mas NÃO se aplica a 'de'; como 'de' tem .many espúrio, vira ORPHAN!
    assert rows["Pts.many"].cells["pt-BR"].kind == CellKind.MISSING
    assert rows["Pts.many"].cells["de"].kind == CellKind.ORPHAN

    # Caso inverso: quando 'de' não tem .many, fica NOT_APPLICABLE (não é MISSING!)
    _write_json(pkg / "lang/de.json", {"Pts": {"one": "{n} Pkt", "other": "{n} Pkte"}})
    session2 = load_package_session(discover_manifest(pkg / "module.json"))
    rows2 = {r.key_path: r for r in session2.rows}
    assert rows2["Pts.many"].cells["pt-BR"].kind == CellKind.MISSING
    assert rows2["Pts.many"].cells["de"].kind == CellKind.NOT_APPLICABLE

