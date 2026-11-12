from __future__ import annotations

from app.core.validator import (
    CustomEnricherRule,
    IgnoredWarning,
    compute_value_hash,
    extract_protected_tokens,
    inspect_base_defects,
    missing_tokens_for_translation,
    validate_translation,
)


def test_cascade_extraction_splits_tech_and_translatable_without_placeholder_collision() -> None:
    text = (
        "{{#if active}}Olá {{actor.name}}, lance "
        "@UUID[Compendium.dnd5e.spells.Item.1]{Bola de Fogo}, "
        "veja @Embed[Compendium.x.y.z caption=\"Mapa da Masmorra\" inline], "
        "role [[/damage 2d6[fire] #Dano de Fogo]], "
        "teste @Check[type:athletics|dc:15|name:Salto em Altura], "
        "aplique &Reference[condition=prone]{Caído} e [[/act stealth dc=18]] "
        "contra <actor> com <dc>15</dc> em https://foundryvtt.com/docs/?a=1#b para {target}.{{/if}}"
    )
    tokens = extract_protected_tokens(text)
    kinds = [t.kind for t in tokens]

    assert "handlebars" in kinds
    assert "enricher" in kinds
    assert "url" in kinds
    assert "html" in kinds
    assert "placeholder" in kinds

    placeholders = [t.raw for t in tokens if t.kind == "placeholder"]
    # Rótulos de enricher ({Bola de Fogo}, {Caído}) e [fire] NÃO podem virar placeholders
    assert placeholders == ["{target}"]

    enrichers = {t.raw: t for t in tokens if t.kind == "enricher"}
    uuid_tok = enrichers["@UUID[Compendium.dnd5e.spells.Item.1]{Bola de Fogo}"]
    assert uuid_tok.tech_key == "@UUID[Compendium.dnd5e.spells.Item.1]"
    assert uuid_tok.translatable_parts == ["Bola de Fogo"]

    embed_tok = next(v for k, v in enrichers.items() if k.startswith("@Embed["))
    assert "Compendium.x.y.z" in embed_tok.tech_key
    assert "Mapa da Masmorra" not in embed_tok.tech_key
    assert embed_tok.translatable_parts == ["Mapa da Masmorra"]

    dmg_tok = enrichers["[[/damage 2d6[fire] #Dano de Fogo]]"]
    assert dmg_tok.tech_key == "[[/damage 2d6[fire]]]"
    assert dmg_tok.translatable_parts == ["Dano de Fogo"]

    chk_tok = enrichers["@Check[type:athletics|dc:15|name:Salto em Altura]"]
    assert "type:athletics" in chk_tok.tech_key and "dc:15" in chk_tok.tech_key
    assert "Salto em Altura" not in chk_tok.tech_key
    assert chk_tok.translatable_parts == ["Salto em Altura"]

    urls = [t.raw for t in tokens if t.kind == "url"]
    assert urls == ["https://foundryvtt.com/docs/?a=1#b"]

    html_raws = [t.raw for t in tokens if t.kind == "html"]
    assert "<actor>" in html_raws
    assert "<dc>" in html_raws
    assert "</dc>" in html_raws


def test_custom_enrichers_and_generic_heuristics() -> None:
    custom = [
        CustomEnricherRule(name="MacroToken", pattern=r"(?P<tech>%[A-Z_]+%)(?:\{(?P<label>[^}]+)\})?"),
        CustomEnricherRule(name="ShadowAt", pattern=r"@UUID\[[^\]]+\]"),
    ]
    base = "Use %HEAL_FULL%{Curar} plus @UUID[Compendium.x.y]{Inner {nested}} @CustomMod[id=7]{Ativar} &SymMod[tier=2] and [[/myact x=1]]."
    tokens = extract_protected_tokens(base, custom_enrichers=custom)
    enrichers = [t for t in tokens if t.kind == "enricher"]

    techs = [t.tech_key for t in enrichers]
    assert "%HEAL_FULL%" in techs
    assert "@UUID[Compendium.x.y]" in techs
    assert "@CustomMod[id=7]" in techs
    assert "&SymMod[tier=2]" in techs
    assert "[[/myact x=1]]" in techs
    assert not any(t.kind == "placeholder" for t in tokens)

    # ignore_empty=False captura célula limpa para "" ao tentar publicar
    empty_crit = validate_translation(
        key_path="K.Empty",
        lang="pt-BR",
        base_text="Hi {name}",
        target_text="",
        ignore_empty=False,
    )
    assert any(i.severity == "critical" and i.rule_id == "placeholder_mismatch" for i in empty_crit)

    # Tag HTML aberta sem fechamento -> html_mismatch
    unclosed = validate_translation(
        key_path="K.Html",
        lang="pt-BR",
        base_text="Plain",
        target_text="<b>Sem fechar",
    )
    assert any(i.rule_id == "html_mismatch" and i.severity == "warning" for i in unclosed)

    bad = validate_translation(
        key_path="K.Custom",
        lang="pt-BR",
        base_text=base,
        target_text="Use %WRONG%{Curar} plus @CustomMod[id=9]{Ativar} &SymMod[tier=2] e [[/myact x=2]].",
        custom_enrichers=custom,
    )
    assert any(i.severity == "critical" and i.rule_id == "enricher_tech_mismatch" for i in bad)


def test_severity_classification_critical_vs_warning_and_free_placeholder_order() -> None:
    base = "Hit {target} with {weapon} and {target} burns! See <b>details</b> at https://ex.com <actor>."

    # Ordem invertida dos placeholders mantendo mesma contagem e mesmas tags/URL -> válido!
    ok_issues = validate_translation(
        key_path="K.Ok",
        lang="pt-BR",
        base_text=base,
        target_text="Com {weapon}, acerte {target} e {target} queima! Veja <b>detalhes</b> em https://ex.com <actor>.",
    )
    assert ok_issues == []

    # Contagem repetida diferente (mesmos nomes únicos) -> Aviso (warning), NÃO crítico
    count_issues = validate_translation(
        key_path="K.Count",
        lang="pt-BR",
        base_text=base,
        target_text="Com {weapon}, acerte {target}! Veja <b>detalhes</b> em https://ex.com <actor>.",
    )
    assert [i.rule_id for i in count_issues] == ["placeholder_count"]
    assert count_issues[0].severity == "warning"

    # Placeholder único faltando -> Crítico
    crit_ph = validate_translation(
        key_path="K.CritPh",
        lang="pt-BR",
        base_text="Hello {actor} ({level})",
        target_text="Olá {actor}",
    )
    assert any(i.rule_id == "placeholder_mismatch" and i.severity == "critical" for i in crit_ph)
    assert missing_tokens_for_translation("Hello {actor} ({level})", "Olá {actor}") == ["{level}"]

    # Handlebars alterado -> Crítico
    crit_hb = validate_translation(
        key_path="K.CritHb",
        lang="pt-BR",
        base_text="Hi {{user.name}}",
        target_text="Olá {{user.nome}}",
    )
    assert any(i.rule_id == "handlebars_mismatch" and i.severity == "critical" for i in crit_hb)

    # HTML divergente/desbalanceado e URL omitida -> Warning
    warn_html_url = validate_translation(
        key_path="K.Warn",
        lang="pt-BR",
        base_text='Go to <a class="btn" href="https://a.test">site</a> and https://b.test',
        target_text='Vá para <a class="other" href="https://a.test">site</i>',
    )
    rule_ids = {i.rule_id: i.severity for i in warn_html_url}
    assert rule_ids.get("url_mismatch") == "warning"
    assert rule_ids.get("html_mismatch") == "warning"


def test_base_defects_detection_and_ignored_warnings_hash_invalidation() -> None:
    base_collision = "Gain @UUID[Compendium.a.b]{power} when {power} activates."
    base_issues = inspect_base_defects(base_collision)
    assert len(base_issues) >= 1
    assert all(i.severity == "info" for i in base_issues)

    # Alerta ignorado para um valor específico é suprimido enquanto texto não muda
    target_v1 = "Olá mundo"
    ignored = [
        IgnoredWarning(
            key_path="K.Ig",
            lang="pt-BR",
            rule_id="placeholder_mismatch",
            value_hash=compute_value_hash(target_v1),
            reason="Intencional",
        )
    ]
    issues_v1 = validate_translation(
        key_path="K.Ig",
        lang="pt-BR",
        base_text="Hello {name}",
        target_text=target_v1,
        ignored_warnings=ignored,
    )
    assert all(i.is_ignored for i in issues_v1)

    # Ao mudar o texto da tradução, value_hash muda e o alerta reativa automaticamente
    issues_v2 = validate_translation(
        key_path="K.Ig",
        lang="pt-BR",
        base_text="Hello {name}",
        target_text="Olá outro mundo",
        ignored_warnings=ignored,
    )
    assert any(not i.is_ignored and i.severity == "critical" for i in issues_v2)

