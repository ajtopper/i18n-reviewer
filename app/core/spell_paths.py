from __future__ import annotations

import ctypes
import json
import os
from pathlib import Path
import shutil
import tempfile

_SENTINEL_WORDS: dict[str, str] = {
    "pt_BR": "casa",
    "es_ES": "casa",
    "fr_FR": "maison",
    "de_DE": "Haus",
    "en_US": "house",
    "en_GB": "house",
}


def default_bundled_hunspell_dir() -> Path:
    """Locate packaged LibreOffice .aff/.dic dictionaries in dev or frozen PyInstaller mode."""
    import sys

    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        cand = Path(str(meipass)) / "resources" / "hunspell"
        if cand.exists():
            return cand
    return Path(__file__).resolve().parents[2] / "resources" / "hunspell"


def windows_short_path(path: Path) -> Path:
    """Convert a path with non-ASCII characters to its Windows 8.3 short path when supported."""
    if os.name != "nt":
        return path
    try:
        raw = str(path)
        buf = ctypes.create_unicode_buffer(1024)
        res = ctypes.windll.kernel32.GetShortPathNameW(raw, buf, len(buf))
        if res > 0 and buf.value:
            return Path(buf.value)
    except (AttributeError, OSError):
        pass
    return path


def is_same_file_or_dir(path_a: Path, path_b: Path) -> bool:
    """Return True when two paths point to the same filesystem entry (even across 8.3 aliases)."""
    try:
        if path_a.exists() and path_b.exists():
            return os.path.samefile(path_a, path_b)
    except OSError:
        pass
    return path_a.resolve() == path_b.resolve()


def _read_settings_ascii_dir(app_data_dir: Path) -> Path | None:
    settings_path = app_data_dir / "settings.json"
    if not settings_path.exists():
        return None
    try:
        data = json.loads(settings_path.read_text(encoding="utf-8-sig"))
        val = data.get("spell_ascii_dir")
        if isinstance(val, str) and val.strip():
            cand = Path(val.strip())
            if str(cand).isascii():
                return cand
    except (OSError, ValueError):
        pass
    return None


def resolve_ascii_enchant_dir(app_data_dir: Path, enchant_dir: Path) -> Path:
    """Resolve an ASCII-safe Enchant directory via Windows 8.3 short path or settings fallback."""
    enchant_dir.mkdir(parents=True, exist_ok=True)
    if str(enchant_dir).isascii():
        return enchant_dir
    short_cand = windows_short_path(enchant_dir)
    if str(short_cand).isascii():
        return short_cand
    configured = _read_settings_ascii_dir(app_data_dir)
    if configured is not None:
        configured.mkdir(parents=True, exist_ok=True)
        return configured
    temp_cand = Path(tempfile.gettempdir()) / "i18n-reviewer-enchant"
    if str(temp_cand).isascii():
        temp_cand.mkdir(parents=True, exist_ok=True)
        return temp_cand
    drive_cand = Path(os.environ.get("SystemDrive", "C:") + "\\i18n-reviewer-enchant")
    drive_cand.mkdir(parents=True, exist_ok=True)
    return drive_cand


def copy_if_newer_or_missing(src: Path, dst: Path) -> None:
    """Copy src to dst only when distinct on disk and missing or newer."""
    if is_same_file_or_dir(src, dst):
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    if not dst.exists() or src.stat().st_mtime > dst.stat().st_mtime:
        shutil.copy2(src, dst)


def stage_hunspell_dictionaries(
    user_enchant_dir: Path,
    effective_enchant_dir: Path,
    bundled_dicts_dir: Path,
) -> None:
    """Populate effective hunspell directory, keeping user dictionaries higher priority."""
    user_hunspell_dir = user_enchant_dir / "hunspell"
    eff_hunspell_dir = effective_enchant_dir / "hunspell"
    eff_hunspell_dir.mkdir(parents=True, exist_ok=True)

    if not is_same_file_or_dir(effective_enchant_dir, user_enchant_dir):
        for item in user_hunspell_dir.glob("*"):
            if item.suffix.lower() in (".aff", ".dic"):
                copy_if_newer_or_missing(item, eff_hunspell_dir / item.name)
        for pwl in user_enchant_dir.glob("pwl_*.txt"):
            copy_if_newer_or_missing(pwl, effective_enchant_dir / pwl.name)

    if bundled_dicts_dir.exists():
        for item in bundled_dicts_dir.glob("*"):
            if item.suffix.lower() in (".aff", ".dic"):
                dst = eff_hunspell_dir / item.name
                if not dst.exists():
                    shutil.copy2(item, dst)


def resolve_sentinel_word(tag: str, effective_hunspell_dir: Path) -> str | None:
    """Return known sentinel word for tag, or sample first entry from a custom .dic."""
    if tag in _SENTINEL_WORDS:
        return _SENTINEL_WORDS[tag]
    dic_path = effective_hunspell_dir / f"{tag}.dic"
    if not dic_path.exists():
        return None
    try:
        for idx, line in enumerate(dic_path.read_text(encoding="utf-8", errors="ignore").splitlines()):
            if idx == 0:
                continue
            word = line.split("/", 1)[0].split("\t", 1)[0].strip()
            if word and len(word) >= 3 and word.isalpha():
                return word
    except OSError:
        return None
    return None

