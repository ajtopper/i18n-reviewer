# i18n Reviewer

Desktop localization review tool built with Python and PySide6 for inspecting, editing, validating, spellchecking, and safely publishing Foundry VTT module/system JSON translation packages while preserving original formatting byte-for-byte.

---

## Features Overview

- **Package & Project Management:** Open Foundry manifests (`module.json` or `system.json`) via **New Project...** or resume saved review sessions (`.i18nproj`) via **Open Project...**, with automatic crash-recovery drafts and external disk-change detection (**Sync now** + three-way conflict resolution).
- **Format-Preserving Surgical JSON Writes:** Uses source byte spans so unmodified keys, indentation, trailing newlines, duplicate-key ordering, and escaping stay intact when publishing to production.
- **Editable Base Column & Stale Propagation:** Edit source-language entries (when editable in the manifest and not using an external file or HTTP-only reference) and automatically mark downstream target translations as `stale` with inline `Before` / `Now` comparison in the Inspector.
- **Technical Token & Enricher Validation:** Protects Handlebars (`{{...}}` / `{{{...}}}`), Foundry `@UUID[...]` / `@Embed[...]` / enrichers, URLs, HTML tags/entities, `{placeholders}`, and user-defined custom regex rules (**Enricher Rules...**).
- **Two-Level Glossary:** Manage global and project-specific terms, source variants, accepted translations, and `do_not_translate` terms (**Glossary...**) with CSV/JSON import & export, filtering, and inline suggestions.
- **Bundled Offline Hunspell Spellchecking:** Live and batch spellchecking for `en_US`, `pt_BR`, `es_ES`, `fr_FR`, and `de_DE` (including the Base column) with technical/glossary masking, context-menu fixes, and a global Personal Word List.
- **Safe Publish & Rollback Pipeline:** **Send to Production** runs SHA-256 disk checks, structural/critical blockers, `.bak` backup batching, atomic file replacement with retry backoff, and partial-failure rollback; **Restore Backup** creates a `pre-restore` backup before restoring prior batches.

---

## Quick Start (From Source)

### Prerequisites

- **Python 3.14+** (`requires-python >= 3.14` in `pyproject.toml`)
- **Windows x64** (recommended/supported packaging target; core tests run in a `.venv` Python environment)

### Setup

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
```

For runtime-only dependencies without dev/test/packaging tools:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### Running the App

```powershell
# Launch the GUI
.\.venv\Scripts\python.exe -m app.main

# Launch and immediately open a package manifest
.\.venv\Scripts\python.exe -m app.main path\to\module.json

# Run headless startup + bundled Hunspell dictionary self-test
.\.venv\Scripts\python.exe -m app.main --self-test
```

### Running Checks

```powershell
.\.venv\Scripts\mypy.exe app
.\.venv\Scripts\python.exe -m pytest -v
```

---

## Reviewer Guide

### 1. Opening a Package or Session

1. Click **New Project...** and select a package manifest (`module.json` or `system.json`).
2. In the configuration dialog, pick the **Base language**, optionally choose an external read-only JSON reference, and toggle any conditional language entries.
3. Click **Save Project (`Ctrl+S`)** to store an `.i18nproj` session file. Application state such as recovery drafts, Personal Word List entries, backup batches, and settings are stored under `%APPDATA%\i18n-reviewer` (or `~/.config/i18n-reviewer` when `APPDATA` is not set).

### 2. Reviewing & Filtering Translations

- **Status Filters:** Switch the toolbar **Filter** dropdown between:
  - `All` — show every row matching language/file/search filters
  - `Pending Only` — rows with target cells that are `missing`, `empty`, `unreviewed`, or `stale` (excluding read-only/structural/orphan-deletion cells)
  - `Edited Only` — rows with unsaved/unpublished local changes
  - `All Alerts` — rows with active critical or warning issues (including Base `spell:*` warnings)
  - `Glossary Mismatches` — rows violating glossary rules
- **Search & File Filter:** Filter rows in real time via the search box (`Ctrl+F`) or scope to a specific JSON source file with the **File** dropdown.
- **Inspector & Dynamic Actions:** Selecting a cell displays source file/line metadata, state (`kind`, review status, dirty flag), `stale` base diffs (`Before` / `Now`), file/validation/spell diagnostics, `Insert: <token>` buttons, and `Ignore this alert (...)` / `Re-enable alert (...)` toggles.
- **Context Menu Actions:**
  - **Target cells:** `Mark as Reviewed`, `Mark Reviewed + Next (Ctrl+Enter)`, `Expanded Editor (Shift+F2)...`, `Revert to production`, `Remove orphan key...` / `Cancel orphan removal`, `Insert missing token: ...`, alert ignore/re-enable toggles, `Apply glossary: <term> → <translation>`, `Add term to glossary...`, spell suggestions (`Fix '<word>' → '<suggestion>'`), and `Add '<word>' to dictionary`.
  - **Base cells:** `Expanded Editor (Shift+F2)...`, `Revert to production`, alert ignore/re-enable toggles, spell suggestions (`Fix '<word>' → '<suggestion>'`), and `Add '<word>' to dictionary`.

### 3. Keyboard Shortcuts

| Shortcut | Action |
| --- | --- |
| `Ctrl+S` | Save current `.i18nproj` project |
| `Ctrl+Z` / `Ctrl+Y` | Undo / Redo cell edit, review, revert, or orphan deletion |
| `Ctrl+F` | Focus search filter input |
| `Ctrl+Enter` | Mark current target cell reviewed and advance to the next pending cell |
| `Ctrl+Down` | Jump to the next pending cell (`missing`, `empty`, `unreviewed`, or `stale`) |
| `Shift+F2` | Open **Expanded Editor** (with token syntax highlighting) |
| `Ctrl+Space` | Open glossary popup on the active table cell or inside the Expanded Editor |

### 4. Validation, Glossary & Spellcheck

- **Custom Enrichers (`Enricher Rules...`):** Add project-level regex patterns to treat custom markup or variables as protected tokens during validation and spellchecking.
- **Ignored Alerts:** Warnings can be muted with an optional justification (`Ignore this alert (...)`). Each ignore rule binds to the content hash of the cell, so editing the text later automatically re-evaluates the warning.
- **Glossary (`Glossary...`):** Define global and project terms, source variants, accepted translations, and **Do Not Translate** terms. Supported import/export formats are JSON and CSV.
- **Hunspell Spellchecking:**
  - Mapped locales: `en` → `en_US`, `pt` / `pt-br` → `pt_BR`, `es` → `es_ES`, `fr` → `fr_FR`, `de` → `de_DE`.
  - Technical spans, URLs, placeholders, and glossary terms/translations are masked automatically before checking prose.
  - Languages missing a dictionary display `(no spellcheck)` in the column header with details in the header tooltip and Inspector.
  - On Windows profiles containing non-ASCII characters, `SpellService` automatically resolves a Windows 8.3 short path (`GetShortPathNameW`) or configurable `spell_ascii_dir` in `%APPDATA%\i18n-reviewer\settings.json` so Enchant/Hunspell can load dictionaries reliably.

### 5. Publishing & Backups

1. Click **Send to Production** to inspect all modified base and target files.
2. Review any **blocking errors** (SHA-256 external disk changes, critical token errors, structural conflicts, pending sync conflicts, or fatal parse errors) and **warnings** (unreviewed changes, base edits impacting downstream targets, duplicate keys, or glossary mismatches).
3. Confirm to create a `.bak` backup batch under `%APPDATA%\i18n-reviewer`, surgically serialize modified JSON files, and atomically replace files on disk (with `PermissionError` backoff retries and automatic/manual rollback on failure).
4. Click **Restore Backup** at any time to restore a previous batch or individual files (a `pre-restore` safety backup is automatically created first, with options to re-sync or discard local drafts).

---

## Windows Build & Packaging

Packaging uses PyInstaller (`spec\build.spec`) to build a `--onedir --windowed` x64 bundle in `dist\i18n-reviewer` containing PySide6, the pruned Enchant/Hunspell runtime, bundled LibreOffice dictionaries (`resources\hunspell` + `en_US.aff`/`.dic`), and `licenses/`.

### Option A: Automated Script (`scripts\package_windows.ps1`)

Builds with PyInstaller, runs `i18n-reviewer.exe --self-test`, and packages a portable ZIP (`dist\i18n-reviewer-<Version>-win64.zip`):

```powershell
.\scripts\package_windows.ps1 -Version 0.1.0
```

Useful flags:

- `-SkipBuild` — Skip rebuilding with PyInstaller and run `--self-test` + packaging against existing `dist\i18n-reviewer\`.
- `-BuildInstaller` — Also invoke Inno Setup (`iscc` must be in `PATH`) using `installer\i18n-reviewer.iss` to produce `dist\i18n-reviewer-<Version>-setup-win64.exe`.

```powershell
.\scripts\package_windows.ps1 -Version 0.1.0 -BuildInstaller
```

### Option B: Manual Build & Verification

```powershell
# 1. Build dist\i18n-reviewer\
.\.venv\Scripts\pyinstaller.exe --clean -y spec\build.spec

# 2. Verify bundled Qt + all 5 Hunspell dictionaries (en_US, pt_BR, es_ES, fr_FR, de_DE)
.\dist\i18n-reviewer\i18n-reviewer.exe --self-test
```

### Third-Party Licenses

Third-party notices and full license texts for bundled dependencies (Qt/PySide6, Enchant/Hunspell, and LibreOffice Hunspell dictionaries) are included in [licenses/THIRD_PARTY_NOTICES.md](licenses/THIRD_PARTY_NOTICES.md) and the `licenses/` directory.
