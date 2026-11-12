# 11: Base Language Publish/Backup Pipeline & Base Spellcheck

**What to build:** Extend production publishing, backup/restore rollback, and Hunspell spellchecking to cover edited base-language files so source fixes can be safely shipped and spellchecked end-to-end. Modified base JSON files appear in **Send to Production** alongside modified target languages, undergo SHA-256 disk checks, structural/critical blocking, duplicate/unreviewed warnings, surgical span-preserving serialization, backup `.bak` batching, atomic writes with retry/partial rollback, and rollback in **Restore Backup** (re-syncing both base and target state). Additionally, the base language column participates in Hunspell spellchecking (using the bundled `en_US` or matching locale dictionary), displaying header spellcheck status, live/batch `spell:*` warnings, Inspector suggestions, context-menu corrections / add-to-dictionary, and `--self-test` verification of `en_US`.

**Blocked by:** 10: Editable Base Column, Stale Propagation & Project Draft/Sync

**Status:** ready-for-agent

- [ ] **Send to Production** detects dirty base-language files, performs SHA-256 external change verification and critical/structural blocking checks on the base file, exposes warning summaries (including downstream impact or unreviewed changes), preserves formatting byte-for-byte via surgical spans, creates `.bak` entries inside the publish backup batch, and atomically writes the base JSON file with partial-failure rollback.
- [ ] **Restore Backup** can restore a base-language file (as part of a batch or single-file selection) after creating a `pre-restore` backup, and correctly re-syncs or discards local base drafts.
- [ ] Hunspell spellchecking runs on the base column during batch validation and live editing (respecting technical/glossary masking and `SpellService` status/missing-dictionary indicators in the Base column header and Inspector).
- [ ] Context menu on base cells exposes validation/base actions, spell suggestions (`Fix '...' → '...'`), and `Add '...' to dictionary` (persisting in the global PWL and revalidating matching cells), plus `Ctrl+Z`/`Ctrl+Y` support for fixes.
- [ ] `--self-test` verifies `en_US` dictionary availability alongside `pt_BR`, `es_ES`, `fr_FR`, and `de_DE` when packaged and run from both normal and non-ASCII paths.
- [ ] Automated tests cover base-file publish/backup/restore (including retry/rollback), base spellcheck + PWL + context-menu fixes, and full `pytest` + `mypy` passing.

