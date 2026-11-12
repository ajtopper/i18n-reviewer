from __future__ import annotations

from pathlib import Path

from app.core.glossary import (
    GlossaryEntry,
    detect_base_glossary_matches,
    export_glossary_csv,
    export_glossary_json,
    import_glossary_csv,
    import_glossary_json,
    lint_translation_glossary,
    load_global_glossary,
    merge_glossaries,
    save_global_glossary,
)
from app.core.validator import CustomEnricherRule, IgnoredWarning, compute_value_hash


def test_two_level_glossary_merge_and_persistence(tmp_path: Path) -> None:
    app_data = tmp_path / "appdata"
    global_entries = [
        GlossaryEntry(
            term="Spell",
            source_variants=["Spells"],
            translations={"pt-BR": ["Magia", "Magias"]},
            notes="Global rule",
        ),
        GlossaryEntry(
            term="Damage",
            translations={"pt-BR": ["Dano"]},
        ),
    ]
    saved_path = save_global_glossary(global_entries, app_data_dir=app_data)
    assert saved_path == app_data / "glossary.json"
    loaded_global = load_global_glossary(app_data_dir=app_data)
    assert loaded_global == global_entries

    project_entries = [
        GlossaryEntry(
            term="spell",
            source_variants=["Spells"],
            translations={"pt-BR": ["Feitiço", "Feitiços"]},
            notes="Project override",
        ),
        GlossaryEntry(
            term="Feat",
            translations={"pt-BR": ["Talento"]},
        ),
    ]
    merged = merge_glossaries(loaded_global, project_entries)
    by_term = {e.term.lower(): e for e in merged}
    assert set(by_term.keys()) == {"spell", "damage", "feat"}
    # Projeto sobrescreve Global mesmo variando caixa quando ambos case_sensitive=False
    assert by_term["spell"].translations["pt-BR"] == ["Feitiço", "Feitiços"]
    assert by_term["spell"].notes == "Project override"


def test_glossary_linter_longest_match_tech_masking_do_not_translate_and_variants() -> None:
    entries = [
        GlossaryEntry(term="Spell", translations={"pt-BR": ["Magia", "Magias"]}),
        GlossaryEntry(term="Spell Slot", source_variants=["Spell Slots"], translations={"pt-BR": ["Espaço de Magia", "Espaços de Magia"]}),
        GlossaryEntry(term="Perception", translations={"pt-BR": ["Percepção"]}),
        GlossaryEntry(term="Foundry VTT", case_sensitive=True, do_not_translate=True),
        GlossaryEntry(term="HP", case_sensitive=True, do_not_translate=True),
    ]

    # 1) "Spell Slot" deve vencer "Spell"; &Reference[Perception] e {Perception} / {{Spell}} / URL são mascarados
    base = (
        "Spend one Spell Slot using &Reference[Perception] and {{Spell}} "
        "on https://example.com/Spell/Slot inside <span class=\"Spell\">Foundry VTT</span> {Spell}."
    )
    matches = detect_base_glossary_matches(base, entries)
    matched_terms = [m.term for m in matches]
    assert "Spell Slot" in matched_terms
    assert "Foundry VTT" in matched_terms
    assert "Spell" not in matched_terms
    assert "Perception" not in matched_terms

    # 2) Célula missing ou vazia não dispara alerta
    assert lint_translation_glossary("K", "pt-BR", base, None, entries) == []
    assert lint_translation_glossary("K", "pt-BR", base, "", entries) == []

    # 3) Aceita variante plural "Espaços de Magia" e termo do_not_translate intacto
    ok_issues = lint_translation_glossary(
        "K",
        "pt-BR",
        base,
        "Gaste seus Espaços de Magia com &Reference[Perception] no Foundry VTT.",
        entries,
    )
    assert ok_issues == []

    # 4) Falta tradução de Spell Slot e alterou caixa de "HP" (case_sensitive + do_not_translate)
    bad_issues = lint_translation_glossary(
        "K",
        "pt-BR",
        "Recover Spell Slots and HP now.",
        "Recupere espaços arcanos e hp agora.",
        entries,
    )
    rules = {i.rule_id: i for i in bad_issues}
    assert "glossary:Spell Slot" in rules
    assert "glossary:HP" in rules
    assert all(i.severity == "warning" for i in bad_issues)

    # 5) Mascaramento não desmascara substring idêntica dentro do caminho UUID técnico!
    assert detect_base_glossary_matches("Use @UUID[Compendium.Spell.1]", entries) == []
    custom = [CustomEnricherRule(name="Macro", pattern=r"%[A-Za-z]+%")]
    assert detect_base_glossary_matches("Run %Spell% now", entries, custom_enrichers=custom) == []

    # 6) IgnoredWarning com value_hash suprime até o texto mudar
    ignored = [
        IgnoredWarning(
            key_path="K",
            lang="pt-BR",
            rule_id="glossary:Spell Slot",
            value_hash=compute_value_hash("Recupere espaços arcanos e HP agora."),
            reason="Adaptação livre",
        )
    ]
    waived = lint_translation_glossary(
        "K",
        "pt-BR",
        "Recover Spell Slots and HP now.",
        "Recupere espaços arcanos e HP agora.",
        entries,
        ignored_warnings=ignored,
    )
    assert len(waived) == 1 and waived[0].is_ignored is True


def test_glossary_csv_and_json_roundtrip(tmp_path: Path) -> None:
    entries = [
        GlossaryEntry(
            term="Saving Throw",
            source_variants=["Saving Throws", "Save"],
            case_sensitive=False,
            do_not_translate=False,
            notes="Com vírgula, aspas \"teste\" e pipe",
            translations={"pt-BR": ["Teste de Resistência", "TR"], "es": ["Tirada de Salvación"]},
        ),
        GlossaryEntry(
            term="VTT",
            case_sensitive=True,
            do_not_translate=True,
        ),
    ]

    json_file = tmp_path / "export.json"
    export_glossary_json(entries, json_file)
    assert import_glossary_json(json_file) == entries

    csv_file = tmp_path / "export.csv"
    export_glossary_csv(entries, csv_file)
    assert import_glossary_csv(csv_file) == entries

