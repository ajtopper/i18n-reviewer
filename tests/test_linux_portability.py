from __future__ import annotations

import os
from pathlib import Path

import pytest

from app import main as app_main
from app.core import project_storage, spell_paths, validator
from app.core.spell_service import SpellService


def test_default_app_data_dir_respects_appdata_xdg_and_home(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    appdata_dir = tmp_path / "roaming"
    xdg_dir = tmp_path / "xdg_cfg"
    fake_home = tmp_path / "home"

    monkeypatch.setenv("APPDATA", str(appdata_dir))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg_dir))
    assert validator.default_app_data_dir() == appdata_dir / "i18n-reviewer"
    assert project_storage.default_app_data_dir() == appdata_dir / "i18n-reviewer"

    monkeypatch.delenv("APPDATA", raising=False)
    assert validator.default_app_data_dir() == xdg_dir / "i18n-reviewer"

    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    monkeypatch.setattr(Path, "home", classmethod(lambda _cls: fake_home))
    assert validator.default_app_data_dir() == fake_home / ".config" / "i18n-reviewer"


def test_resolve_ascii_enchant_dir_keeps_posix_non_ascii_path_without_drive_fallback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    non_ascii_app = tmp_path / "usuário_ação" / "i18n-reviewer"
    enchant_dir = non_ascii_app / "enchant"

    monkeypatch.setattr(spell_paths.os, "name", "posix")
    resolved = spell_paths.resolve_ascii_enchant_dir(non_ascii_app, enchant_dir)

    assert resolved == enchant_dir
    assert enchant_dir.exists()
    assert "i18n-reviewer-enchant" not in str(resolved)


def test_bundled_hunspell_contains_all_five_locales_and_loads_en_us(tmp_path: Path) -> None:
    hunspell_dir = spell_paths.default_bundled_hunspell_dir()
    for locale in ("en_US", "pt_BR", "es_ES", "fr_FR", "de_DE"):
        assert (hunspell_dir / f"{locale}.aff").is_file()
        assert (hunspell_dir / f"{locale}.dic").is_file()

    svc = SpellService(app_data_dir=tmp_path / "appdata")
    assert svc.is_available("en")
    assert svc.check("en", "house")
    assert app_main.run_self_test(app_data_dir=tmp_path / "selftest") == 0
