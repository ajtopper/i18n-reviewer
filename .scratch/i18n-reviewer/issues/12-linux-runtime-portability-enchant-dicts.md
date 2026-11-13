# 12: Linux Runtime Portability, Enchant Discovery & Offline `en_US` Dictionaries

**What to build:** Ensure the application runs natively on Linux without Windows-specific filesystem or spellchecker assumptions. Configuration and recovery paths respect `XDG_CONFIG_HOME` (falling back to `~/.config/i18n-reviewer`), spellchecker directory resolution handles POSIX non-ASCII user paths cleanly without Windows drive fallbacks, the bundled `en_US` Hunspell dictionary is available offline alongside `pt_BR`, `es_ES`, `fr_FR`, and `de_DE` without relying on Windows-only wheel data, and CI validates `mypy`, `pytest`, and `--self-test` on Linux (`ubuntu-24.04`) in addition to Windows.

**Blocked by:** None (can start immediately)

**Status:** done

- [x] Application data directory resolution supports `XDG_CONFIG_HOME` on Linux/POSIX before falling back to `~/.config/i18n-reviewer`, while preserving `%APPDATA%` behavior on Windows.
- [x] POSIX spellchecker directory resolution handles non-ASCII paths cleanly without creating Windows drive paths (`C:\...`).
- [x] Bundled offline Hunspell dictionaries include `en_US` alongside `pt_BR`, `es_ES`, `fr_FR`, and `de_DE` so `--self-test` passes offline on Linux without requiring distro dictionary packages.
- [x] Automated tests cover POSIX/XDG directory resolution, non-ASCII POSIX spell path handling, and `en_US` offline dictionary availability.
- [x] CI runs `mypy`, `pytest`, and headless `--self-test` on both Windows and Linux (`ubuntu-24.04`).
