# Changelog

All notable changes to **i18n Reviewer** will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.0] - 2026-11-12

### Added

- **Native Qt 6 Design System & Light/Dark Theme Engine:**
  - Centralized Stitch-inspired emerald/neutral palette using Qt 6 `Fusion` style, `QPalette`, and modular QSS (`app/ui/theme.py`).
  - Automatic OS Light/Dark mode detection and live updates via `QStyleHints.colorScheme()`, plus a manual `Auto / Light / Dark` selector persisted in `settings.json`.
  - Theme-aware semantic color tokens for `StatusCellDelegate` status badges/stripes and `TokenHighlighter` syntax highlighting.
- **UI Layout Redesign & Vector Iconography:**
  - Collapsible left sidebar with synchronized quick status filters and package JSON file list.
  - Table context sub-bar displaying active filter breadcrumbs, live filtered key count pill, and `Compact` row-density toggle.
  - Card-based Inspector layout (`Key Metadata & Location`, `Validation & Diagnostics`, and action footer with highlighted `Mark Reviewed + Next`).
  - Adaptive vector icons across toolbar, sidebar, and action buttons via `QtAwesome`.
  - Live comparison prototype script (`scripts/ui_prototype.py`).
- **Batch Multi-Cell Review:**
  - Support Shift/Ctrl multi-cell selection for **Mark Reviewed** and **Mark Reviewed + Next (`Ctrl+Enter`)**, marking all eligible selected language cells in a single undoable/redoable macro, displaying live batch counts, and advancing to the next pending cell after the selection.

### Changed

- Removed hardcoded light-only inline stylesheets from banners, `StatusCellDelegate`, `TokenHighlighter`, and `ExpandedEditorDialog` so all surfaces adapt cleanly to Dark mode.

## [0.1.0] - 2026-11-12

Initial release of **i18n Reviewer** for Foundry VTT users, translators, and module/system developers.

### Added

- **Foundry VTT Package & Project Workflow:**
  - Open `module.json` and `system.json` manifests via **New Project...**, select base language, optionally attach an external read-only JSON base, and toggle conditional language entries.
  - Multi-file target unification, CLDR plural group handling, and orphan key detection/removal.
  - Save/resume `.i18nproj` sessions (`schema_version = 1`), automatic crash-recovery drafts under `%APPDATA%\i18n-reviewer`, file watcher disk-change alerts (**Sync now**), and three-way merge conflict resolution dialog.
- **Review Table, Editable Base Column & Navigation:**
  - Side-by-side table view with status filters (`All`, `Pending Only`, `Edited Only`, `All Alerts`, `Glossary Mismatches`), real-time search (`Ctrl+F`), file filter, and per-language visibility toggles.
  - Inline editing and **Expanded Editor (`Shift+F2`)** with token syntax highlighting (`TokenHighlighter`), `QUndoStack` undo/redo (`Ctrl+Z` / `Ctrl+Y`), `Mark Reviewed + Next (Ctrl+Enter)`, and `Next Pending (Ctrl+Down)`.
  - Editable Base column (when editable in the manifest and not backed by an external/HTTP reference) with automatic `stale` propagation and `Before` / `Now` diff display in the Inspector.
- **Format-Preserving Production Publish & Backup/Restore:**
  - Byte-span JSON parser and surgical serializer preserving indentation, trailing newlines, escaping, and duplicate-key ordering.
  - **Send to Production** pipeline covering both modified target and base files: SHA-256 external change checks, critical/structural/pending-sync blockers, warning summaries, grouped `.bak` batches, atomic `.tmp` + `os.replace` writes with `PermissionError` backoff retries, and partial-failure rollback.
  - **Restore Backup** dialog creating a `pre-restore` safety backup and supporting three-way conflict re-sync or local draft discard.
- **Validation, Glossary & Offline Hunspell Spellchecking:**
  - Protection and validation for Handlebars (`{{...}}` / `{{{...}}}`), Foundry enrichers (`@UUID[...]`, `@Embed[...]`, etc.), HTML tags/entities, URLs, `{placeholders}`, and user-defined regex rules (**Enricher Rules...**).
  - Hash-bound alert ignore/re-enable toggles with optional justification.
  - Two-level glossary (**Glossary...**, `Ctrl+Space` popup, context-menu apply/add, JSON/CSV import & export) with longest-match and `do_not_translate` linting.
  - Offline Hunspell spellchecking across target columns and the Base column (`en_US`, `pt_BR`, `es_ES`, `fr_FR`, `de_DE`), technical/glossary masking, context-menu fixes (`Fix '...' → '...'`), global Personal Word List (`Add '...' to dictionary`), `(no spellcheck)` header/Inspector indicators, and Windows 8.3/`spell_ascii_dir` non-ASCII path handling.
- **UI Localization, Packaging, CI & Docs:**
  - Complete International English interface and automated UI i18n check.
  - Windows x64 PyInstaller `--onedir --windowed` bundle (`spec/build.spec`), headless `--self-test`, packaging script (`scripts/package_windows.ps1`), Inno Setup script (`installer/i18n-reviewer.iss`), and third-party license notices (`licenses/THIRD_PARTY_NOTICES.md`).
  - GitHub Actions CI (`.github/workflows/ci.yml`) and tag-driven Windows `.exe`/`.zip` Release workflow (`.github/workflows/release.yml`), `MIT` `LICENSE`, and `README.md`.

