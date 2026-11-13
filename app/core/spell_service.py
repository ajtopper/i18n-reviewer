from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import re
import shutil
import threading
from typing import Callable, Protocol

import enchant

from app.core.glossary import GlossaryEntry, mask_glossary_phrases, mask_technical_spans
from app.core.spell_paths import (
    default_bundled_hunspell_dir,
    is_same_file_or_dir,
    resolve_ascii_enchant_dir,
    resolve_sentinel_word,
    stage_hunspell_dictionaries,
)
from app.core.validator import (
    CustomEnricherRule,
    IgnoredWarning,
    ValidationIssue,
    build_ignored_map,
    default_app_data_dir,
)

_LANG_TO_ENCHANT: dict[str, str] = {
    "pt-br": "pt_BR",
    "pt": "pt_BR",
    "es": "es_ES",
    "fr": "fr_FR",
    "de": "de_DE",
    "en": "en_US",
}

_WORD_RE = re.compile(r"[^\W_]+(?:[-'’][^\W_]+)*")


class EnchantDictLike(Protocol):
    """Minimal Enchant dictionary interface wrapped behind SpellService."""

    def check(self, word: str) -> bool: ...
    def suggest(self, word: str) -> list[str]: ...
    def add(self, word: str) -> None: ...


DictFactory = Callable[[str, Path, enchant.Broker], EnchantDictLike]


@dataclass(frozen=True)
class SpellDictStatus:
    """Availability and diagnostic status of a language's spellcheck dictionary."""

    lang: str
    enchant_tag: str
    available: bool
    message: str = ""


def _default_dict_factory(tag: str, pwl_path: Path, broker: enchant.Broker) -> EnchantDictLike:
    pwl_path.parent.mkdir(parents=True, exist_ok=True)
    if not pwl_path.exists():
        pwl_path.write_text("", encoding="utf-8")
    return enchant.DictWithPWL(tag, str(pwl_path), broker=broker)


class SpellService:
    """Thread-safe Hunspell wrapper via pyenchant with non-ASCII Windows workaround and PWL."""

    def __init__(
        self,
        app_data_dir: Path | None = None,
        *,
        bundled_dicts_dir: Path | None = None,
        dict_factory: DictFactory | None = None,
    ) -> None:
        self.app_data_dir = app_data_dir or default_app_data_dir()
        self.bundled_dicts_dir = bundled_dicts_dir or default_bundled_hunspell_dir()
        self._dict_factory: DictFactory = dict_factory or _default_dict_factory
        self._lock = threading.RLock()

        self.user_enchant_dir = self.app_data_dir / "enchant"
        self.user_hunspell_dir = self.user_enchant_dir / "hunspell"
        self.user_hunspell_dir.mkdir(parents=True, exist_ok=True)

        self.effective_enchant_dir = resolve_ascii_enchant_dir(self.app_data_dir, self.user_enchant_dir)
        self.effective_hunspell_dir = self.effective_enchant_dir / "hunspell"
        stage_hunspell_dictionaries(
            self.user_enchant_dir,
            self.effective_enchant_dir,
            self.bundled_dicts_dir,
        )

        os.environ["ENCHANT_CONFIG_DIR"] = str(self.effective_enchant_dir)
        meipass = getattr(__import__("sys"), "_MEIPASS", None)
        if meipass:
            enchant_prefix = Path(str(meipass)) / "enchant_prefix"
            if enchant_prefix.exists() and hasattr(enchant, "set_prefix_dir"):
                enchant.set_prefix_dir(str(enchant_prefix))
        self._broker = enchant.Broker()
        self._broker.set_ordering("*", "hunspell")
        self._dicts: dict[str, EnchantDictLike | None] = {}
        self._statuses: dict[str, SpellDictStatus] = {}
        self._word_cache: dict[tuple[str, str], bool] = {}

    def map_lang_to_enchant(self, lang: str) -> str:
        """Resolve Foundry language tag into an Enchant Hunspell dictionary tag."""
        clean = lang.strip()
        if not clean:
            return ""
        mapped = _LANG_TO_ENCHANT.get(clean.lower())
        if mapped:
            return mapped
        norm = clean.replace("-", "_")
        with self._lock:
            if self._broker.dict_exists(norm):
                return norm
            available_tags = [tag for tag, _ in self._broker.list_dicts()]
        primary = norm.split("_", 1)[0].lower()
        for cand in available_tags:
            if cand.lower() == clean.lower() or cand.split("_", 1)[0].lower() == primary:
                return cand
        return norm

    def _missing_dict_status(self, lang: str, tag: str) -> SpellDictStatus:
        return SpellDictStatus(
            lang=lang,
            enchant_tag=tag,
            available=False,
            message=(
                f"No Hunspell dictionary for '{lang}'. "
                f"Copy {tag or lang}.aff/.dic to '{self.user_hunspell_dir}'."
            ),
        )

    def _ensure_loaded(self, lang: str) -> tuple[str, EnchantDictLike | None]:
        with self._lock:
            if lang in self._statuses:
                tag = self._statuses[lang].enchant_tag
                return tag, self._dicts.get(tag)

            tag = self.map_lang_to_enchant(lang)
            if not tag or not self._broker.dict_exists(tag):
                self._statuses[lang] = self._missing_dict_status(lang, tag)
                return tag, None

            pwl_path = self.effective_enchant_dir / f"pwl_{tag}.txt"
            try:
                dct = self._dict_factory(tag, pwl_path, self._broker)
            except Exception as exc:
                self._statuses[lang] = SpellDictStatus(
                    lang=lang,
                    enchant_tag=tag,
                    available=False,
                    message=f"Failed to open dictionary '{tag}': {exc}",
                )
                return tag, None

            sentinel = resolve_sentinel_word(tag, self.effective_hunspell_dir)
            if sentinel is not None and not dct.check(sentinel):
                self._statuses[lang] = SpellDictStatus(
                    lang=lang,
                    enchant_tag=tag,
                    available=False,
                    message=(
                        f"Sentinel word check failed ('{sentinel}') when opening '{tag}'. "
                        f"Check ASCII path or reinstall in '{self.user_hunspell_dir}'."
                    ),
                )
                return tag, None

            self._dicts[tag] = dct
            self._statuses[lang] = SpellDictStatus(lang=lang, enchant_tag=tag, available=True)
            return tag, dct

    def status_for(self, lang: str, *, open_dict: bool = True) -> SpellDictStatus:
        """Return availability status and human message for a language."""
        if open_dict:
            self._ensure_loaded(lang)
            return self._statuses[lang]
        with self._lock:
            if lang in self._statuses:
                return self._statuses[lang]
            tag = self.map_lang_to_enchant(lang)
            if tag and self._broker.dict_exists(tag):
                return SpellDictStatus(lang=lang, enchant_tag=tag, available=True)
            return self._missing_dict_status(lang, tag)

    def is_available(self, lang: str) -> bool:
        """True if a working sentinel-verified dictionary is loaded for lang."""
        return self.status_for(lang, open_dict=True).available

    def check(self, lang: str, word: str) -> bool:
        """Check whether a single word is accepted in lang (True if dict unavailable)."""
        tag, dct = self._ensure_loaded(lang)
        if dct is None:
            return True
        query = word.replace("’", "'")
        cache_key = (tag, query)
        with self._lock:
            cached = self._word_cache.get(cache_key)
            if cached is not None:
                return cached
            ok = bool(dct.check(query))
            if len(self._word_cache) > 50000:
                self._word_cache.clear()
            self._word_cache[cache_key] = ok
            return ok

    def suggest(self, lang: str, word: str, limit: int = 6) -> list[str]:
        """Compute spelling suggestions on demand (never invoked during batch checking)."""
        _tag, dct = self._ensure_loaded(lang)
        if dct is None:
            return []
        query = word.replace("’", "'")
        with self._lock:
            return list(dct.suggest(query))[:limit]

    def add_personal(self, lang: str, word: str) -> bool:
        """Add word to the global PWL for lang in ENCHANT_CONFIG_DIR."""
        clean = word.strip().replace("’", "'")
        if not clean:
            return False
        tag, dct = self._ensure_loaded(lang)
        if dct is None:
            return False
        with self._lock:
            dct.add(clean)
            eff_pwl = self.effective_enchant_dir / f"pwl_{tag}.txt"
            user_pwl = self.user_enchant_dir / f"pwl_{tag}.txt"
            if eff_pwl.exists() and not is_same_file_or_dir(eff_pwl, user_pwl):
                shutil.copy2(eff_pwl, user_pwl)
            for k in [key for key in self._word_cache if key[0] == tag]:
                del self._word_cache[k]
        return True

    def check_text(
        self,
        lang: str,
        target_text: str | None,
        *,
        base_text: str | None = None,
        glossary_entries: list[GlossaryEntry] | None = None,
        custom_enrichers: list[CustomEnricherRule] | None = None,
    ) -> list[str]:
        """Return ordered unknown words in target_text after filtering tech spans, noise, base words, and glossary."""
        if not target_text or not self.is_available(lang):
            return []

        masked = mask_technical_spans(target_text, custom_enrichers=custom_enrichers)
        if glossary_entries:
            masked = mask_glossary_phrases(masked, lang, glossary_entries)

        base_words_folded: set[str] = set()
        if base_text:
            base_masked = mask_technical_spans(base_text, custom_enrichers=custom_enrichers)
            for btok in _WORD_RE.findall(base_masked):
                base_words_folded.add(btok.casefold())
                base_words_folded.add(btok.strip("-'’").casefold())

        unknown: list[str] = []
        seen: set[str] = set()
        for word in _WORD_RE.findall(masked):
            clean = word.strip("-'’")
            if not clean or len(clean) <= 2:
                continue
            if any(ch.isdigit() for ch in clean):
                continue
            if clean.isupper():
                continue
            norm_key = word.casefold()
            if norm_key in base_words_folded or clean.casefold() in base_words_folded:
                continue
            if norm_key in seen:
                continue
            if not self.check(lang, word):
                seen.add(norm_key)
                unknown.append(word)
        return unknown

    def lint_cell_spelling(
        self,
        key_path: str,
        lang: str,
        base_text: str | None,
        target_text: str | None,
        *,
        glossary_entries: list[GlossaryEntry] | None = None,
        custom_enrichers: list[CustomEnricherRule] | None = None,
        ignored_warnings: list[IgnoredWarning] | None = None,
    ) -> list[ValidationIssue]:
        """Check cell spelling without calling suggest(), returning non-blocking warning ValidationIssues."""
        unknown = self.check_text(
            lang,
            target_text,
            base_text=base_text,
            glossary_entries=glossary_entries,
            custom_enrichers=custom_enrichers,
        )
        if not unknown:
            return []
        ignored_map = build_ignored_map(ignored_warnings, key_path, lang, target_text)
        issues: list[ValidationIssue] = []
        for word in unknown:
            rule_id = f"spell:{word}"
            ig = ignored_map.get(rule_id)
            issues.append(
                ValidationIssue(
                    rule_id=rule_id,
                    severity="warning",
                    message=f"Possible spelling error: '{word}'.",
                    missing_tokens=[word],
                    is_ignored=ig is not None,
                    ignored_reason=ig.reason if ig is not None else "",
                )
            )
        return issues
