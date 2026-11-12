from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from app.core.glossary import (
    GlossaryEntry,
    deserialize_glossary_entries,
    serialize_glossary_entries,
)
from app.core.project_manager import (
    CellData,
    CellKind,
    FileSnapshot,
    LoadedFileInfo,
    PackageSession,
    ReviewStatus,
    TableRowData,
    discover_manifest,
    load_package_session,
    propagate_base_change,
)
from app.core.validator import CustomEnricherRule, IgnoredWarning

CURRENT_SCHEMA_VERSION = 1
ConflictChoice = Literal["keep_local", "accept_disk", "manual"]


class PackageNotFoundError(FileNotFoundError):
    """Raised when neither relative nor absolute package root exists on disk."""


class UnsupportedProjectVersionError(ValueError):
    """Raised when a .i18nproj file has a newer schema_version than supported."""


@dataclass(frozen=True)
class SyncConflict:
    """Real 3-way conflict on a single (key_path, target_lang) cell."""

    key_path: str
    lang: str
    snapshot_value: str | None
    disk_value: str | None
    local_value: str | None
    base_text: str | None
    was_deletion_draft: bool = False


@dataclass(frozen=True)
class ConflictResolution:
    """User choice for resolving a single SyncConflict."""

    key_path: str
    lang: str
    choice: ConflictChoice
    manual_value: str | None = None


@dataclass
class SyncReport:
    """Summary of synchronizing disk files against saved snapshots and local drafts."""

    changed_files: list[str] = field(default_factory=list)
    blocked_files: list[str] = field(default_factory=list)
    auto_absorbed_count: int = 0
    converged_count: int = 0
    stale_marked_count: int = 0
    conflicts: list[SyncConflict] = field(default_factory=list)


@dataclass
class SyncPreview:
    """Staged synchronization result applied to the live session only after conflicts are confirmed."""

    fresh_session: PackageSession
    report: SyncReport


@dataclass
class LoadedProjectResult:
    """Result returned when opening an existing .i18nproj file."""

    session: PackageSession
    sync_report: SyncReport
    migrated_from: int | None = None


def default_app_data_dir() -> Path:
    """Return per-user application data directory (%APPDATA%\\i18n-reviewer on Windows)."""
    appdata = os.environ.get("APPDATA")
    if appdata:
        return Path(appdata) / "i18n-reviewer"
    return Path.home() / ".config" / "i18n-reviewer"


def atomic_write_text(target: Path, content: str) -> None:
    """Write text to a temporary sibling file and atomically replace target."""
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = target.with_name(f"{target.name}.tmp")
    tmp_path.write_text(content, encoding="utf-8")
    os.replace(tmp_path, target)


def resolve_loaded_file_path(session: PackageSession, loaded_file: LoadedFileInfo) -> Path | None:
    """Resolve physical disk path for a LoadedFileInfo (internal to package or external base)."""
    if (
        session.base_external_path is not None
        and loaded_file.lang == session.base_lang
        and loaded_file.rel_path == session.base_external_path.name
    ):
        return session.base_external_path
    return session.manifest.package_root / loaded_file.rel_path


def _compute_rel_path(target: Path, anchor_dir: Path) -> str | None:
    try:
        return os.path.relpath(target, anchor_dir).replace("\\", "/")
    except ValueError:
        return None


def _collect_drafts_and_review_state(
    session: PackageSession,
) -> tuple[dict[str, dict[str, str]], dict[str, list[str]], dict[str, dict[str, dict[str, Any]]]]:
    edits: dict[str, dict[str, str]] = {}
    deletions: dict[str, list[str]] = {}
    review_state: dict[str, dict[str, dict[str, Any]]] = {}

    for row in session.rows:
        if (
            row.base_cell is not None
            and row.base_cell.local_value != row.base_cell.prod_value
            and row.base_cell.local_value is not None
        ):
            edits.setdefault(session.base_lang, {})[row.key_path] = row.base_cell.local_value

        for lang, cell in row.cells.items():
            if cell.marked_for_deletion:
                deletions.setdefault(lang, []).append(row.key_path)
            elif cell.local_value != cell.prod_value and cell.local_value is not None:
                edits.setdefault(lang, {})[row.key_path] = cell.local_value

            if cell.review_status != "unreviewed" or cell.previous_base is not None:
                entry: dict[str, Any] = {"status": cell.review_status}
                if cell.previous_base is not None:
                    entry["previous_base"] = cell.previous_base
                review_state.setdefault(lang, {})[row.key_path] = entry

    return edits, deletions, review_state


def _serialize_validation_config(session: PackageSession) -> dict[str, Any]:
    return {
        "ignored_warnings": [
            {
                "key_path": iw.key_path,
                "lang": iw.lang,
                "rule_id": iw.rule_id,
                "value_hash": iw.value_hash,
                "reason": iw.reason,
            }
            for iw in session.ignored_warnings
        ],
        "custom_enrichers": [
            {"name": ce.name, "pattern": ce.pattern}
            for ce in session.custom_enrichers
        ],
        "project_glossary": serialize_glossary_entries(session.project_glossary),
    }


def _load_validation_config(
    raw: dict[str, Any],
) -> tuple[list[IgnoredWarning], list[CustomEnricherRule], list[GlossaryEntry]]:
    ignored: list[IgnoredWarning] = []
    for item in raw.get("ignored_warnings", []) or []:
        if not isinstance(item, dict):
            continue
        ignored.append(
            IgnoredWarning(
                key_path=str(item.get("key_path", "")),
                lang=str(item.get("lang", "")),
                rule_id=str(item.get("rule_id", "")),
                value_hash=str(item.get("value_hash", "")),
                reason=str(item.get("reason", "")),
            )
        )
    customs: list[CustomEnricherRule] = []
    for item in raw.get("custom_enrichers", []) or []:
        if not isinstance(item, dict):
            continue
        customs.append(
            CustomEnricherRule(
                name=str(item.get("name", "")),
                pattern=str(item.get("pattern", "")),
            )
        )
    glossary = deserialize_glossary_entries(raw.get("project_glossary", []))
    return ignored, customs, glossary


def _serialize_project_payload(session: PackageSession, project_dir: Path | None) -> dict[str, Any]:
    pkg_root = session.manifest.package_root
    pkg_rel = _compute_rel_path(pkg_root, project_dir) if project_dir is not None else None
    ext_rel = (
        _compute_rel_path(session.base_external_path, project_dir)
        if (project_dir is not None and session.base_external_path is not None)
        else None
    )
    edits, deletions, review_state = _collect_drafts_and_review_state(session)

    files_meta = [
        {
            "lang": e.lang,
            "path": e.path,
            "conditional": e.conditional,
            "enabled": e.path in session.enabled_paths,
        }
        for e in session.manifest.entries
        if e.editable
    ]

    return {
        "schema_version": CURRENT_SCHEMA_VERSION,
        "project_id": session.project_id,
        "package": {
            "manifest_type": session.manifest.manifest_type,
            "manifest_name": session.manifest.manifest_path.name,
            "package_id": session.manifest.package_id,
            "package_root_rel": pkg_rel,
            "package_root_abs": str(pkg_root),
            "base_lang": session.base_lang,
            "base_external_rel": ext_rel,
            "base_external_path": str(session.base_external_path) if session.base_external_path else None,
            "target_langs": list(session.target_langs),
            "files": files_meta,
            "missing_target_mapping": dict(session.missing_target_mapping),
        },
        "snapshots": {
            "files": {
                rel_path: {
                    "sha256": snap.sha256,
                    "entries": snap.entries,
                }
                for rel_path, snap in session.file_snapshots.items()
            }
        },
        "drafts": {
            "edits": edits,
            "deletions": deletions,
        },
        "review_state": review_state,
        **_serialize_validation_config(session),
    }


def _recovery_path(project_id: str, app_data_dir: Path | None = None) -> Path:
    base = app_data_dir or default_app_data_dir()
    return base / "recovery" / f"{project_id}.json"


def write_recovery_draft(session: PackageSession, app_data_dir: Path | None = None) -> Path:
    """Persist an auto-recovery draft for the current session under %APPDATA%."""
    edits, deletions, review_state = _collect_drafts_and_review_state(session)
    payload = {
        "schema_version": CURRENT_SCHEMA_VERSION,
        "project_id": session.project_id,
        "drafts": {"edits": edits, "deletions": deletions},
        "review_state": review_state,
        **_serialize_validation_config(session),
    }
    path = _recovery_path(session.project_id, app_data_dir)
    atomic_write_text(path, json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
    return path


def has_recovery_draft(project_id: str, app_data_dir: Path | None = None) -> bool:
    return _recovery_path(project_id, app_data_dir).exists()


def clear_recovery_draft(project_id: str, app_data_dir: Path | None = None) -> None:
    path = _recovery_path(project_id, app_data_dir)
    if path.exists():
        path.unlink()


def save_project_file(
    session: PackageSession,
    project_path: Path,
    app_data_dir: Path | None = None,
) -> None:
    """Save the session atomically as a .i18nproj file and clear its recovery draft."""
    resolved_proj = project_path.resolve()
    payload = _serialize_project_payload(session, resolved_proj.parent)
    atomic_write_text(resolved_proj, json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
    session.project_path = resolved_proj
    clear_recovery_draft(session.project_id, app_data_dir=app_data_dir)


def _migrate_schema_if_needed(raw: dict[str, Any], project_path: Path) -> int | None:
    version = int(raw.get("schema_version", 1))
    if version > CURRENT_SCHEMA_VERSION:
        raise UnsupportedProjectVersionError(
            f"Project schema_version {version} is newer than supported version {CURRENT_SCHEMA_VERSION}."
        )
    if version == CURRENT_SCHEMA_VERSION:
        return None
    backup_path = project_path.with_name(f"{project_path.name}.v{version}.bak")
    atomic_write_text(backup_path, json.dumps(raw, indent=2, ensure_ascii=False) + "\n")
    raw["schema_version"] = CURRENT_SCHEMA_VERSION
    return version


def _resolve_package_root(
    pkg_meta: dict[str, Any],
    project_dir: Path,
    relocated_root: Path | None,
) -> Path:
    manifest_name = str(pkg_meta.get("manifest_name") or f"{pkg_meta.get('manifest_type', 'module')}.json")
    if relocated_root is not None:
        cand = relocated_root.resolve()
        if (cand / manifest_name).exists() or (cand / "module.json").exists() or (cand / "system.json").exists():
            return cand
        raise PackageNotFoundError(f"Manifest not found under relocated folder '{cand}'.")

    rel = pkg_meta.get("package_root_rel")
    if isinstance(rel, str) and rel:
        cand = (project_dir / rel).resolve()
        if (cand / manifest_name).exists():
            return cand

    abs_str = pkg_meta.get("package_root_abs")
    if isinstance(abs_str, str) and abs_str:
        cand = Path(abs_str).resolve()
        if (cand / manifest_name).exists():
            return cand

    raise PackageNotFoundError("Could not locate Foundry package root from relative or absolute paths.")


def _reapply_local_draft(
    cell: CellData,
    draft_val: str | None,
    draft_del: bool,
    base_text: str | None,
) -> None:
    if draft_del and cell.kind == CellKind.ORPHAN:
        cell.set_marked_for_deletion(True)
    elif draft_val is not None:
        cell.apply_edit(draft_val, base_text=base_text)


def _mark_stale_if_base_changed(
    cell: CellData,
    base_text_changed: bool,
    old_base_text: str | None,
    report: SyncReport,
) -> None:
    if base_text_changed and cell.review_status == "reviewed":
        cell.review_status = "stale"
        cell.previous_base = old_base_text
        report.stale_marked_count += 1


def _sync_base_row(
    row: TableRowData,
    *,
    base_lang: str,
    base_changed: bool,
    base_blocked: bool,
    base_source_editable: bool,
    snap_base: str | None,
    base_draft: str | None,
    report: SyncReport,
) -> tuple[bool, str | None, str | None]:
    """Synchronize one row's base_cell with disk changes, local drafts, and 3-way conflicts."""
    base_cell = row.base_cell
    disk_base = base_cell.prod_value if base_cell is not None else row.base_text

    def _apply_draft() -> str | None:
        if base_cell is not None and base_draft is not None:
            if base_cell.kind == CellKind.MISSING and base_source_editable:
                base_cell.readonly = False
            if base_cell.can_edit() and base_cell.apply_edit(base_draft, base_text=None):
                row.set_base_text(base_cell.local_value)
        return row.base_text

    if not base_changed or base_blocked:
        new_base = _apply_draft() if base_draft is not None else row.base_text
        return False, snap_base, new_base

    if base_draft is None:
        changed = snap_base != disk_base
        if changed:
            report.auto_absorbed_count += 1
        return changed, snap_base, row.base_text

    if disk_base == snap_base:
        return False, snap_base, _apply_draft()

    if base_draft == disk_base:
        report.converged_count += 1
        return False, snap_base, row.base_text

    report.conflicts.append(
        SyncConflict(
            key_path=row.key_path,
            lang=base_lang,
            snapshot_value=snap_base,
            disk_value=disk_base,
            local_value=base_draft,
            base_text=disk_base,
            was_deletion_draft=False,
        )
    )
    return False, snap_base, _apply_draft()


def _apply_saved_state_and_sync(
    session: PackageSession,
    saved_snapshots: dict[str, FileSnapshot],
    drafts: dict[str, Any],
    review_state: dict[str, Any],
) -> SyncReport:
    """Restore saved drafts/review_state onto a freshly loaded session and merge any disk changes."""
    report = SyncReport()
    edits: dict[str, dict[str, str]] = drafts.get("edits", {})
    deletions: dict[str, list[str]] = drafts.get("deletions", {})

    blocked_langs: set[str] = set()
    for lf in session.files:
        if lf.has_fatal_error:
            report.blocked_files.append(lf.rel_path)
            blocked_langs.add(lf.lang)

    saved_base_entries: dict[str, str] = {}
    saved_target_entries: dict[str, dict[str, str]] = {lang: {} for lang in session.target_langs}
    changed_langs: set[str] = set()

    for lf in session.files:
        old_snap = saved_snapshots.get(lf.rel_path)
        if old_snap is None:
            continue
        if lf.lang == session.base_lang:
            saved_base_entries.update(old_snap.entries)
        elif lf.lang in saved_target_entries:
            saved_target_entries[lf.lang].update(old_snap.entries)
        if lf.has_fatal_error or (old_snap.sha256 and lf.sha256 != old_snap.sha256):
            report.changed_files.append(lf.rel_path)
            changed_langs.add(lf.lang)

    base_changed = session.base_lang in changed_langs
    base_blocked = session.base_lang in blocked_langs
    base_source_editable = (
        session.base_external_path is None
        and not base_blocked
        and any(e.lang == session.base_lang and e.editable for e in session.manifest.entries)
    )

    for row in session.rows:
        key = row.key_path
        base_draft = edits.get(session.base_lang, {}).get(key)
        base_text_changed, old_base_text, new_base_text = _sync_base_row(
            row,
            base_lang=session.base_lang,
            base_changed=base_changed,
            base_blocked=base_blocked,
            base_source_editable=base_source_editable,
            snap_base=saved_base_entries.get(key),
            base_draft=base_draft,
            report=report,
        )

        for lang, cell in row.cells.items():
            lang_review = review_state.get(lang, {}).get(key, {})
            saved_status: ReviewStatus = lang_review.get("status", "unreviewed")
            saved_prev_base: str | None = lang_review.get("previous_base")
            draft_val = edits.get(lang, {}).get(key)
            draft_del = key in deletions.get(lang, [])

            if lang not in changed_langs or lang in blocked_langs:
                _reapply_local_draft(cell, draft_val, draft_del, new_base_text)
                cell.review_status = saved_status
                cell.previous_base = saved_prev_base
                _mark_stale_if_base_changed(cell, base_text_changed, old_base_text, report)
            else:
                snap_val = saved_target_entries.get(lang, {}).get(key)
                disk_val = cell.prod_value
                has_local_draft = (draft_val is not None) or draft_del

                if not has_local_draft:
                    if disk_val != snap_val:
                        report.auto_absorbed_count += 1
                        cell.review_status = "unreviewed"
                    else:
                        cell.review_status = saved_status
                        cell.previous_base = saved_prev_base
                    _mark_stale_if_base_changed(cell, base_text_changed, old_base_text, report)
                elif disk_val == snap_val:
                    _reapply_local_draft(cell, draft_val, draft_del, new_base_text)
                    cell.review_status = saved_status
                    cell.previous_base = saved_prev_base
                    _mark_stale_if_base_changed(cell, base_text_changed, old_base_text, report)
                elif (draft_del and disk_val is None) or (not draft_del and draft_val == disk_val):
                    report.converged_count += 1
                    cell.review_status = saved_status
                    _mark_stale_if_base_changed(cell, base_text_changed, old_base_text, report)
                else:
                    report.conflicts.append(
                        SyncConflict(
                            key_path=key,
                            lang=lang,
                            snapshot_value=snap_val,
                            disk_value=disk_val,
                            local_value=draft_val,
                            base_text=new_base_text,
                            was_deletion_draft=draft_del,
                        )
                    )
                    _reapply_local_draft(cell, draft_val, draft_del, new_base_text)

            cell._recompute_kind(new_base_text)

    return report


def _resolve_base_conflict(row_data: TableRowData, res: ConflictResolution) -> None:
    base_cell = row_data.base_cell
    if base_cell is None:
        return
    if res.choice == "accept_disk":
        old_base = row_data.base_text
        if base_cell.revert_to_production(base_text=None):
            row_data.set_base_text(base_cell.local_value)
            propagate_base_change(row_data, old_base, is_revert=False)
        elif base_cell.kind == CellKind.MISSING:
            base_cell.readonly = True
            row_data.set_base_text(None)
            propagate_base_change(row_data, old_base, is_revert=False)
    elif res.choice == "manual" and res.manual_value is not None:
        row_data.apply_base_edit(res.manual_value)


def apply_conflict_resolutions(
    session: PackageSession,
    resolutions: list[ConflictResolution],
) -> None:
    """Apply user-chosen conflict resolutions onto a PackageSession."""
    row_map = {r.key_path: r for r in session.rows}
    for res in resolutions:
        session.pending_conflict_keys.discard((res.key_path, res.lang))
        row_data = row_map.get(res.key_path)
        if row_data is None:
            continue
        if res.lang == session.base_lang:
            _resolve_base_conflict(row_data, res)
            continue
        cell = row_data.cells.get(res.lang)
        if cell is None:
            continue
        if res.choice == "accept_disk":
            cell.revert_to_production(base_text=row_data.base_text)
        elif res.choice == "manual" and res.manual_value is not None:
            if cell.marked_for_deletion:
                cell.set_marked_for_deletion(False)
            cell.apply_edit(res.manual_value, base_text=row_data.base_text)


def prepare_disk_sync(session: PackageSession) -> SyncPreview:
    """Load fresh disk files and compute 3-way merge without mutating session yet."""
    edits, deletions, review_state = _collect_drafts_and_review_state(session)
    selected = [
        e for e in session.manifest.entries if e.editable and e.path in session.enabled_paths
    ]
    fresh = load_package_session(
        session.manifest,
        base_lang=session.base_lang,
        selected_entries=selected,
        base_external_path=session.base_external_path,
    )
    fresh.project_id = session.project_id
    fresh.project_path = session.project_path
    fresh.missing_target_mapping = dict(session.missing_target_mapping)
    fresh.ignored_warnings = list(session.ignored_warnings)
    fresh.custom_enrichers = list(session.custom_enrichers)
    fresh.project_glossary = list(session.project_glossary)
    report = _apply_saved_state_and_sync(
        fresh,
        saved_snapshots=session.file_snapshots,
        drafts={"edits": edits, "deletions": deletions},
        review_state=review_state,
    )
    return SyncPreview(fresh_session=fresh, report=report)


def commit_sync_preview(session: PackageSession, preview: SyncPreview) -> None:
    """Swap synchronized state from preview into the active PackageSession."""
    if preview.report.blocked_files:
        return
    fresh = preview.fresh_session
    session.files = fresh.files
    session.rows = fresh.rows
    session.warnings = fresh.warnings
    session.file_diagnostics = fresh.file_diagnostics
    session.fatal_files_by_lang = fresh.fatal_files_by_lang
    session.file_snapshots = fresh.file_snapshots
    session.pending_conflict_keys.clear()


def synchronize_session_with_disk(session: PackageSession) -> SyncReport:
    """Convenience helper that prepares and immediately commits disk sync when unblocked."""
    preview = prepare_disk_sync(session)
    if not preview.report.blocked_files:
        commit_sync_preview(session, preview)
    return preview.report


def check_external_disk_changes(session: PackageSession) -> list[str]:
    """Compare current disk SHA-256 hashes against session.file_snapshots."""
    changed: list[str] = []
    for lf in session.files:
        snap = session.file_snapshots.get(lf.rel_path)
        if snap is None:
            continue
        disk_path = resolve_loaded_file_path(session, lf)
        if disk_path is None or not disk_path.exists():
            changed.append(lf.rel_path)
            continue
        disk_hash = hashlib.sha256(disk_path.read_bytes()).hexdigest()
        if disk_hash != snap.sha256:
            changed.append(lf.rel_path)
    return changed


def load_project_file(
    project_path: Path,
    relocated_root: Path | None = None,
    apply_recovery_dir: Path | None = None,
) -> LoadedProjectResult:
    """Load a .i18nproj file, resolving package paths, migrating schema, and syncing disk changes."""
    resolved_proj = project_path.resolve()
    raw = json.loads(resolved_proj.read_text(encoding="utf-8-sig"))
    migrated_from = _migrate_schema_if_needed(raw, resolved_proj)

    pkg_meta = raw.get("package", {})
    pkg_root = _resolve_package_root(pkg_meta, resolved_proj.parent, relocated_root)
    manifest_name = str(pkg_meta.get("manifest_name") or f"{pkg_meta.get('manifest_type', 'module')}.json")
    manifest_path = pkg_root / manifest_name
    if not manifest_path.exists():
        manifest_path = pkg_root / ("module.json" if (pkg_root / "module.json").exists() else "system.json")

    manifest = discover_manifest(manifest_path)
    files_meta = pkg_meta.get("files", [])
    enabled_set = {f["path"] for f in files_meta if f.get("enabled", True)}
    selected = [e for e in manifest.entries if e.editable and (not enabled_set or e.path in enabled_set)]

    ext_path: Path | None = None
    ext_rel = pkg_meta.get("base_external_rel")
    ext_abs = pkg_meta.get("base_external_path")
    if isinstance(ext_rel, str) and ext_rel:
        cand = (resolved_proj.parent / ext_rel).resolve()
        if cand.exists():
            ext_path = cand
    if ext_path is None and isinstance(ext_abs, str) and ext_abs:
        cand = Path(ext_abs).resolve()
        if cand.exists():
            ext_path = cand

    session = load_package_session(
        manifest,
        base_lang=str(pkg_meta.get("base_lang") or manifest.default_base_lang),
        selected_entries=selected,
        base_external_path=ext_path,
    )
    session.project_id = str(raw.get("project_id") or session.project_id)
    session.project_path = resolved_proj
    raw_mapping = pkg_meta.get("missing_target_mapping")
    if isinstance(raw_mapping, dict):
        session.missing_target_mapping = {str(k): str(v) for k, v in raw_mapping.items()}

    drafts = raw.get("drafts", {})
    review_state = raw.get("review_state", {})
    ignored_warnings, custom_enrichers, project_glossary = _load_validation_config(raw)

    if apply_recovery_dir is not None and has_recovery_draft(session.project_id, apply_recovery_dir):
        rec_raw = json.loads(_recovery_path(session.project_id, apply_recovery_dir).read_text(encoding="utf-8"))
        drafts = rec_raw.get("drafts", drafts)
        review_state = rec_raw.get("review_state", review_state)
        if any(k in rec_raw for k in ("ignored_warnings", "custom_enrichers", "project_glossary")):
            ignored_warnings, custom_enrichers, project_glossary = _load_validation_config(rec_raw)

    session.ignored_warnings = ignored_warnings
    session.custom_enrichers = custom_enrichers
    session.project_glossary = project_glossary

    raw_snaps = raw.get("snapshots", {}).get("files", {})
    saved_snapshots = {
        str(rel): FileSnapshot(
            sha256=str(snap_obj.get("sha256", "")),
            entries={str(k): str(v) for k, v in snap_obj.get("entries", {}).items()},
        )
        for rel, snap_obj in raw_snaps.items()
    }
    report = _apply_saved_state_and_sync(
        session,
        saved_snapshots=saved_snapshots,
        drafts=drafts,
        review_state=review_state,
    )
    return LoadedProjectResult(
        session=session,
        sync_report=report,
        migrated_from=migrated_from,
    )
