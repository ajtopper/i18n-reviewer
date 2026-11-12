from __future__ import annotations

import json
from pathlib import Path

from app.core.glossary import GlossaryEntry
from app.core.spell_service import SpellService


def test_spell_service_supports_four_languages_hyphens_apostrophes_and_missing_lang(
    tmp_path: Path,
) -> None:
    app_data = tmp_path / "appdata"
    svc = SpellService(app_data_dir=app_data)

    # pt-BR, es, fr, de devem abrir passando pela palavra-sentinela
    for lang in ("pt-BR", "es", "fr", "de"):
        assert svc.is_available(lang), f"Dicionário ausente para {lang}: {svc.status_for(lang)}"

    # Palavras válidas com hífen e apóstrofo são aceitas
    assert svc.check_text("pt-BR", "O guarda-costas usou feitiço.", base_text="Bodyguard used spell.") == []
    assert svc.check_text("es", "El daño mágico fue grande.", base_text="Magical damage.") == []
    assert svc.check_text("fr", "L'arme est peut-être prête.", base_text="The weapon is maybe ready.") == []
    assert svc.check_text("de", "Der Angriffswurf trifft das Haus.", base_text="Attack roll hits.") == []

    # Erros de grafia disparam avisos e suggest() só sob demanda retorna correções
    bad_pt = svc.check_text("pt-BR", "O feitisso falhou", base_text="Spell failed")
    assert "feitisso" in bad_pt
    sugg_pt = svc.suggest("pt-BR", "feitisso")
    assert any("feitiç" in s.lower() or "feitic" in s.lower() for s in sugg_pt)

    # Idioma sem dicionário instalado (eo) fica desligado com aviso amigável
    assert svc.is_available("eo") is False
    assert svc.check_text("eo", "xyzqwerty", base_text="anything") == []
    status_eo = svc.status_for("eo")
    assert status_eo.available is False
    assert "hunspell" in status_eo.message.lower()


def test_spell_service_filters_technical_noise_glossary_and_persists_pwl(
    tmp_path: Path,
) -> None:
    app_data = tmp_path / "appdata"
    svc = SpellService(app_data_dir=app_data)

    glossary = [
        GlossaryEntry(term="Spell", translations={"pt-BR": ["Zorgonarcano"]}),
        GlossaryEntry(term="Nevermore", do_not_translate=True),
    ]
    base = "Use Hearthbound 1d20 {{var}} @UUID[Item.x]{x} https://ex.com"
    text = (
        "O RPG da Hearthbound causa 1d20 ft XP em {{var}} "
        "@UUID[Compendium.invalidword.1]{x} <b>HTMLTAG</b> https://badsite.invalid/typo "
        "com Zorgonarcano de Nevermore."
    )
    # Todos acima devem ser ignorados: técnicos, <=2 letras (em, ft, XP), maiúsculas (RPG), números/dados (1d20),
    # idêntica à base (Hearthbound), e termos do glossário (Zorgonarcano, Nevermore)!
    unknown = svc.check_text("pt-BR", text, base_text=base, glossary_entries=glossary)
    assert unknown == []

    # Palavra inventada que não está nos filtros é detectada -> add_personal persiste no PWL global
    assert svc.check_text("pt-BR", "Palavra Inventadaxx aqui", base_text="Some word") == ["Inventadaxx"]
    svc.add_personal("pt-BR", "Inventadaxx")
    assert svc.check_text("pt-BR", "Palavra Inventadaxx aqui", base_text="Some word") == []

    # Nova instância reabre com o mesmo PWL salvo em ENCHANT_CONFIG_DIR
    svc2 = SpellService(app_data_dir=app_data)
    assert svc2.check_text("pt-BR", "Palavra Inventadaxx aqui", base_text="Some word") == []


def test_spell_service_non_ascii_path_workaround_and_sentinel_validation(
    tmp_path: Path,
    monkeypatch: object,
) -> None:
    non_ascii_app_data = tmp_path / "pasta ção éç"
    svc = SpellService(app_data_dir=non_ascii_app_data)
    assert svc.is_available("pt-BR") is True
    assert svc.check("pt-BR", "casa") is True
    # add_personal em caminho não-ASCII resolvido por 8.3 não pode lançar SameFileError
    assert svc.check("pt-BR", "PalavraUnicaxx") is False
    assert svc.add_personal("pt-BR", "PalavraUnicaxx") is True
    assert svc.check("pt-BR", "PalavraUnicaxx") is True

    # Simula ambiente onde GetShortPathNameW não produz caminho ASCII -> fallback em settings.json assume
    ascii_fallback = tmp_path / "ascii_cfg"
    non_ascii2 = tmp_path / "outro diretório ção"
    non_ascii2.mkdir(parents=True, exist_ok=True)
    (non_ascii2 / "settings.json").write_text(
        json.dumps({"spell_ascii_dir": str(ascii_fallback)}),
        encoding="utf-8",
    )
    monkeypatch.setattr("app.core.spell_paths.windows_short_path", lambda p: p)  # type: ignore[attr-defined]
    svc_fb = SpellService(app_data_dir=non_ascii2)
    assert svc_fb.is_available("pt-BR") is True
    assert svc_fb.check("pt-BR", "casa") is True

    # Falha controlada quando palavra-sentinela falha ao validar dicionário
    class _BrokenDict:
        def check(self, _w: str) -> bool:
            return False

        def suggest(self, _w: str) -> list[str]:
            return []

        def add(self, _w: str) -> None:
            pass

    svc_broken = SpellService(app_data_dir=tmp_path / "broken_sentinel", dict_factory=lambda *_a: _BrokenDict())
    assert svc_broken.is_available("pt-BR") is False
    assert "sentinela" in svc_broken.status_for("pt-BR").message.lower()

