# 10: Editable Base Column, Stale Propagation & Project Draft/Sync

**What to build:** The manifest-declared local base language becomes editable directly in the review grid and in the Expanded Editor so reviewers or package authors can fix source-text typos without leaving the tool. Remote HTTP bases and external reference JSON bases chosen at package open remain read-only. Editing a base cell records `EDITED` / dirty state, supports `Undo` / `Redo` / `Revert to production`, immediately revalidates target translations against the updated source string, transitions already-`reviewed` target translations in that row to `STALE` with `Before` / `Now` comparison (restoring cleanly on revert/undo when appropriate), and persists base drafts and 3-way external change detection/conflict resolution across `.i18nproj` save/open and crash recovery.

**Blocked by:** 03: Persistência (.i18nproj portable), recovery e merge de 3 vias, 05: Proteção de placeholders/HTML/enrichers, ignorados com hash e destaque no editor, 06: Glossário em dois níveis (Global + Projeto), linter, Ctrl+Space e CSV, 08: Tradução completa da interface e mensagens para Inglês Internacional

**Status:** done

- [x] Local manifest-declared base language cells are editable inline (`F2`) and in the Expanded Editor (`Shift+F2`); cells missing from the base, non-string values, structural conflicts, remote HTTP entries, and external reference JSON bases remain read-only with clear Inspector state labels.
- [x] Editing a base cell updates `EDITED` styling/status, supports `QUndoStack` (`Undo`/`Redo`) and `Revert to production`, updates Inspector diagnostics/source metadata, and updates row search/filter matching.
- [x] Updating a base string immediately revalidates base defects and target-language placeholders, HTML/URL checks, and glossary matches in the affected row, and marks any `reviewed` target translations in that row as `STALE` with `Before` / `Now` details.
- [x] Local base edits and review state persist cleanly in `.i18nproj` and crash-recovery drafts without breaking backwards compatibility with existing `.i18nproj` v1 project files.
- [x] Package-open sync, `QFileSystemWatcher` detection, `Sync now` 3-way merge, and the external conflict resolution dialog handle modified base-language keys on disk alongside target-language keys.
- [x] Automated tests cover base cell editability boundaries, undo/revert, stale propagation, `.i18nproj` + recovery persistence, 3-way merge conflicts on base keys, and Qt UI interactions.

