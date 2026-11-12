from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import time
from typing import Any, Callable, Literal

from app.core.glossary import (
    lint_translation_glossary,
    load_global_glossary,
    merge_glossaries,
)
from app.core.json_handler import FileStyle, ParsedLangDocument, apply_surgical_edits, parse_lang_bytes
from app.core.project_manager import (
    CellKind,
    FileSnapshot,
    PackageSession,
    check_external_disk_changes,
    default_app_data_dir,
)
from app.core.project_storage import (
    SyncPreview,
    commit_sync_preview,
    prepare_disk_sync,
)
from app.core.validator import validate_translation

DEFAULT_BACKUP_RETENTION = 30
_RETRY_BACKOFFS = (0.1, 0.2, 0.3, 0.4, 0.5)

ReplaceFn = Callable[[Path, Path], Any]
SleepFn = Callable[[float], Any]
BatchKind = Literal["publish", "pre-restore"]


@dataclass(frozen=True)
class BackupFileEntry:
    """Single backed-up localization file inside a grouped batch."""

    rel_path: str
    backup_name: str
    sha256: str


@dataclass(frozen=True)
class BackupBatch:
    """Grouped snapshot batch stored under %APPDATA%\\i18n-reviewer\\backups\\<project_id>."""

    batch_id: str
    created_at: str
    kind: BatchKind
    files: list[BackupFileEntry]
    batch_dir: Path


@dataclass
class PublishFilePlan:
    """Computed pre-publish payload and diagnostics for a single dirty target file."""

    lang: str
    rel_path: str
    target_path: Path
    edited_keys: dict[str, str] = field(default_factory=dict)
    deleted_keys: set[str] = field(default_factory=set)
    unreviewed_dirty_keys: list[str] = field(default_factory=list)
    duplicate_keys: list[str] = field(default_factory=list)
    validation_warnings: list[str] = field(default_factory=list)
    blocking_reasons: list[str] = field(default_factory=list)
    candidate_bytes: bytes = b""

    @property
    def is_blocked(self) -> bool:
        return bool(self.blocking_reasons)


@dataclass
class PublishPlan:
    """Pre-publish plan covering all modified target files in a session."""

    file_plans: list[PublishFilePlan] = field(default_factory=list)
    external_changes: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class IoOptions:
    """Bundled storage directory and atomic replacement hooks for disk I/O."""

    app_data_dir: Path | None = None
    replace_fn: ReplaceFn = os.replace
    sleep_fn: SleepFn = time.sleep


@dataclass
class PublishResult:
    """Outcome of executing a publish plan."""

    batch_id: str | None = None
    published_files: list[str] = field(default_factory=list)
    published_plans: list[PublishFilePlan] = field(default_factory=list)
    failed_file: str | None = None
    error: str | None = None


@dataclass
class RestoreResult:
    """Outcome of restoring a backup batch or individual file."""

    restored_files: list[str] = field(default_factory=list)
    pre_restore_batch_id: str | None = None
    blocked_files: list[str] = field(default_factory=list)
    sync_preview: SyncPreview | None = None


def get_backup_retention(app_data_dir: Path | None = None) -> int:
    """Read backup_retention from settings.json (default 30)."""
    base = app_data_dir or default_app_data_dir()
    settings_path = base / "settings.json"
    if not settings_path.exists():
        return DEFAULT_BACKUP_RETENTION
    try:
        data = json.loads(settings_path.read_text(encoding="utf-8"))
        val = int(data.get("backup_retention", DEFAULT_BACKUP_RETENTION))
        return max(1, val)
    except (OSError, ValueError, TypeError):
        return DEFAULT_BACKUP_RETENTION


def project_backups_dir(project_id: str, app_data_dir: Path | None = None) -> Path:
    base = app_data_dir or default_app_data_dir()
    return base / "backups" / project_id


def atomic_write_bytes_with_retry(
    target: Path,
    payload: bytes,
    replace_fn: ReplaceFn = os.replace,
    sleep_fn: SleepFn = time.sleep,
) -> None:
    """Write bytes to sibling .tmp file and atomically replace target with up to 5 retries."""
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = target.with_name(f"{target.name}.tmp")
    tmp_path.write_bytes(payload)
    last_exc: OSError | None = None
    for attempt, delay in enumerate(_RETRY_BACKOFFS, start=1):
        try:
            replace_fn(tmp_path, target)
            return
        except PermissionError as exc:
            last_exc = exc
            if attempt < len(_RETRY_BACKOFFS):
                sleep_fn(delay)
    if tmp_path.exists():
        try:
            tmp_path.unlink()
        except OSError:
            pass
    assert last_exc is not None
    raise last_exc


def _sanitize_backup_name(rel_path: str) -> str:
    return rel_path.replace("/", "__").replace("\\", "__") + ".bak"


def _create_backup_batch(
    project_id: str,
    package_root: Path,
    rel_paths: list[str],
    kind: BatchKind,
    app_data_dir: Path | None = None,
) -> BackupBatch:
    root = project_backups_dir(project_id, app_data_dir)
    root.mkdir(parents=True, exist_ok=True)

    now = datetime.now()
    stamp = now.strftime("%Y-%m-%d_%H%M%S")
    seq = 1
    while True:
        batch_id = f"{stamp}_{seq:03d}"
        batch_dir = root / batch_id
        if not batch_dir.exists():
            break
        seq += 1
    batch_dir.mkdir(parents=True, exist_ok=False)

    entries: list[BackupFileEntry] = []
    for rel_path in rel_paths:
        src = package_root / rel_path
        if not src.exists():
            continue
        raw = src.read_bytes()
        sha = hashlib.sha256(raw).hexdigest()
        bak_name = _sanitize_backup_name(rel_path)
        (batch_dir / bak_name).write_bytes(raw)
        entries.append(BackupFileEntry(rel_path=rel_path, backup_name=bak_name, sha256=sha))

    created_at = now.isoformat(timespec="seconds")
    manifest = {
        "batch_id": batch_id,
        "created_at": created_at,
        "kind": kind,
        "files": [
            {"rel_path": e.rel_path, "backup_name": e.backup_name, "sha256": e.sha256}
            for e in entries
        ],
    }
    (batch_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    _enforce_retention(project_id, app_data_dir=app_data_dir)
    return BackupBatch(
        batch_id=batch_id,
        created_at=created_at,
        kind=kind,
        files=entries,
        batch_dir=batch_dir,
    )


def _enforce_retention(project_id: str, app_data_dir: Path | None = None) -> None:
    retention = get_backup_retention(app_data_dir)
    batches = list_backup_batches(project_id, app_data_dir=app_data_dir)
    for stale_batch in batches[retention:]:
        shutil.rmtree(stale_batch.batch_dir, ignore_errors=True)


def list_backup_batches(project_id: str, app_data_dir: Path | None = None) -> list[BackupBatch]:
    """List backup batches for a project ordered from newest to oldest."""
    root = project_backups_dir(project_id, app_data_dir)
    if not root.exists():
        return []
    batches: list[BackupBatch] = []
    for sub in sorted(root.iterdir(), key=lambda p: p.name, reverse=True):
        manifest_path = sub / "manifest.json"
        if not sub.is_dir() or not manifest_path.exists():
            continue
        try:
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
            files = [
                BackupFileEntry(
                    rel_path=str(item["rel_path"]),
                    backup_name=str(item["backup_name"]),
                    sha256=str(item["sha256"]),
                )
                for item in data.get("files", [])
            ]
            kind_raw = str(data.get("kind", "publish"))
            kind: BatchKind = "pre-restore" if kind_raw == "pre-restore" else "publish"
            batches.append(
                BackupBatch(
                    batch_id=str(data.get("batch_id", sub.name)),
                    created_at=str(data.get("created_at", "")),
                    kind=kind,
                    files=files,
                    batch_dir=sub,
                )
            )
        except (OSError, ValueError, KeyError):
            continue
    return batches


def delete_backup_batch(
    project_id: str,
    batch_id: str,
    app_data_dir: Path | None = None,
) -> bool:
    """Delete a specific backup batch directory."""
    batch_dir = project_backups_dir(project_id, app_data_dir) / batch_id
    if not batch_dir.exists():
        return False
    shutil.rmtree(batch_dir)
    return True


@dataclass
class _FilePublishBucket:
    lang: str
    edits: dict[str, str] = field(default_factory=dict)
    deletions: set[str] = field(default_factory=set)
    unreviewed: list[str] = field(default_factory=list)
    structural_conflicts: list[str] = field(default_factory=list)
    pending_sync_conflicts: list[str] = field(default_factory=list)
    validation_criticals: list[str] = field(default_factory=list)
    validation_warnings: list[str] = field(default_factory=list)


def resolve_target_file_for_key(
    session: PackageSession,
    lang: str,
    base_source_file: str = "",
) -> str | None:
    """Resolve the target localization file for inserting a missing key in a language."""
    lang_files = [lf for lf in session.files if lf.lang == lang]
    if not lang_files:
        return None
    if len(lang_files) == 1:
        return lang_files[0].rel_path

    valid_rels = {lf.rel_path for lf in lang_files}
    if base_source_file:
        base_norm = base_source_file.replace("\\", "/")
        mirrored = re.sub(
            rf"(^|[/._-]){re.escape(session.base_lang)}(?=$|[/._-])",
            rf"\1{lang}",
            base_norm,
        )
        if mirrored != base_norm and mirrored in valid_rels:
            return mirrored

        base_name = Path(base_norm).name
        name_matches = [lf.rel_path for lf in lang_files if Path(lf.rel_path).name == base_name]
        if len(name_matches) == 1:
            return name_matches[0]

    mapped = session.missing_target_mapping.get(lang)
    if mapped and mapped in valid_rels:
        return mapped

    for lf in lang_files:
        if not lf.missing_on_disk:
            return lf.rel_path
    return lang_files[0].rel_path


def _base_fallback_style(session: PackageSession) -> FileStyle | None:
    for lf in session.files:
        if lf.lang == session.base_lang and lf.document is not None:
            return lf.document.style
    return None


def prepare_publish_plan(
    session: PackageSession,
    app_data_dir: Path | None = None,
) -> PublishPlan:
    """Validate dirty target files, detect external changes, and build candidate JSON payloads in memory."""
    external = check_external_disk_changes(session)
    base_order = [r.key_path for r in session.rows if not r.is_orphan_row]
    fallback_style = _base_fallback_style(session)
    glossary_entries = merge_glossaries(
        load_global_glossary(app_data_dir),
        session.project_glossary,
    )

    buckets: dict[str, _FilePublishBucket] = {}
    row_by_key = {r.key_path: r for r in session.rows}

    for row in session.rows:
        for lang, cell in row.cells.items():
            if not cell.is_dirty:
                continue
            rel_path = cell.source_file or resolve_target_file_for_key(
                session, lang, row.base_source_file
            )
            if not rel_path:
                continue
            bucket = buckets.setdefault(rel_path, _FilePublishBucket(lang=lang))
            if (row.key_path, lang) in session.pending_conflict_keys:
                bucket.pending_sync_conflicts.append(row.key_path)
            if cell.kind == CellKind.STRUCTURAL_CONFLICT:
                bucket.structural_conflicts.append(row.key_path)
                continue
            if cell.marked_for_deletion:
                bucket.deletions.add(row.key_path)
            elif cell.local_value is not None:
                bucket.edits[row.key_path] = cell.local_value
                if cell.review_status in ("unreviewed", "stale"):
                    bucket.unreviewed.append(row.key_path)
                val_issues = validate_translation(
                    row.key_path,
                    lang,
                    row.base_text,
                    cell.local_value,
                    custom_enrichers=session.custom_enrichers,
                    ignored_warnings=session.ignored_warnings,
                    ignore_empty=False,
                )
                for issue in val_issues:
                    if issue.is_ignored:
                        continue
                    if issue.severity == "critical":
                        bucket.validation_criticals.append(f"{row.key_path}: {issue.message}")
                    elif issue.severity == "warning":
                        bucket.validation_warnings.append(f"{row.key_path}: {issue.message}")
                for g_issue in lint_translation_glossary(
                    row.key_path,
                    lang,
                    row.base_text,
                    cell.local_value,
                    glossary_entries,
                    custom_enrichers=session.custom_enrichers,
                    ignored_warnings=session.ignored_warnings,
                ):
                    if not g_issue.is_ignored:
                        bucket.validation_warnings.append(f"{row.key_path}: {g_issue.message}")

    for conflict_key, conflict_lang in sorted(session.pending_conflict_keys):
        crow = row_by_key.get(conflict_key)
        ccell = crow.cells.get(conflict_lang) if crow is not None else None
        base_src = crow.base_source_file if crow is not None else ""
        crel = (ccell.source_file if ccell is not None else "") or resolve_target_file_for_key(
            session, conflict_lang, base_src
        )
        if crel and crel in buckets:
            bucket = buckets[crel]
            if conflict_key not in bucket.pending_sync_conflicts:
                bucket.pending_sync_conflicts.append(conflict_key)

    loaded_by_rel = {lf.rel_path: lf for lf in session.files}
    plans: list[PublishFilePlan] = []

    for rel_path, bucket in buckets.items():
        target_path = session.manifest.package_root / rel_path
        lf = loaded_by_rel.get(rel_path)
        fp = PublishFilePlan(
            lang=bucket.lang,
            rel_path=rel_path,
            target_path=target_path,
            edited_keys=bucket.edits,
            deleted_keys=bucket.deletions,
            unreviewed_dirty_keys=bucket.unreviewed,
            validation_warnings=bucket.validation_warnings,
        )

        if bucket.validation_criticals:
            fp.blocking_reasons.append(
                f"Critical validation errors ({len(bucket.validation_criticals)}): "
                + "; ".join(bucket.validation_criticals[:5])
            )
        if bucket.pending_sync_conflicts:
            fp.blocking_reasons.append(
                f"Pending sync conflict on keys: {', '.join(bucket.pending_sync_conflicts)}"
            )
        if bucket.structural_conflicts:
            fp.blocking_reasons.append(
                f"Leaf vs. object structural conflict on keys: {', '.join(bucket.structural_conflicts)}"
            )
        if lf is None or lf.has_fatal_error or lf.document is None:
            fp.blocking_reasons.append(f"File '{rel_path}' is invalid or missing on disk.")
            plans.append(fp)
            continue

        fp.duplicate_keys = [d.key_path for d in lf.document.duplicates]
        if not fp.blocking_reasons:
            try:
                fp.candidate_bytes = apply_surgical_edits(
                    lf.document.raw_bytes,
                    edits=bucket.edits,
                    deletions=bucket.deletions,
                    base_order=base_order,
                    fallback_style=fallback_style,
                )
            except ValueError as exc:
                fp.blocking_reasons.append(str(exc))

        plans.append(fp)

    return PublishPlan(file_plans=plans, external_changes=external)


def _snapshot_from_bytes(rel_path: str, raw: bytes) -> tuple[ParsedLangDocument, FileSnapshot]:
    doc = parse_lang_bytes(raw, source_file=rel_path)
    digest = hashlib.sha256(raw).hexdigest()
    snap = FileSnapshot(
        sha256=digest,
        entries={
            k: e.value
            for k, e in doc.entries.items()
            if e.is_string and e.value is not None
        },
    )
    return doc, snap


def _refresh_file_snapshots_from_disk_bytes(
    session: PackageSession,
    updates: list[tuple[str, bytes]],
) -> None:
    loaded_by_rel = {lf.rel_path: lf for lf in session.files}
    for rel_path, raw in updates:
        doc, snap = _snapshot_from_bytes(rel_path, raw)
        lf = loaded_by_rel.get(rel_path)
        if lf is not None:
            lf.document = doc
            lf.sha256 = snap.sha256
            lf.missing_on_disk = False
        session.file_snapshots[rel_path] = snap


def commit_publish_result(session: PackageSession, result: PublishResult) -> None:
    """Apply published file plans into session snapshots and promoted cell production values."""
    if not result.published_plans:
        return
    published_rels = {fp.rel_path for fp in result.published_plans}
    _refresh_file_snapshots_from_disk_bytes(
        session,
        [(fp.rel_path, fp.candidate_bytes) for fp in result.published_plans],
    )

    for row in session.rows:
        for lang, cell in row.cells.items():
            eff_rel = cell.source_file or resolve_target_file_for_key(
                session, lang, row.base_source_file
            )
            if eff_rel not in published_rels:
                continue
            session.pending_conflict_keys.discard((row.key_path, lang))
            if cell.marked_for_deletion:
                cell.clear_after_deletion()
            elif cell.is_dirty and eff_rel:
                cell.mark_published(eff_rel, base_text=row.base_text)


def execute_publish_plan(
    session: PackageSession,
    selected_plans: list[PublishFilePlan],
    app_data_dir: Path | None = None,
    replace_fn: ReplaceFn = os.replace,
    sleep_fn: SleepFn = time.sleep,
) -> PublishResult:
    """Create backup batch and atomically write selected file plans to production."""
    writable = [fp for fp in selected_plans if not fp.is_blocked]
    if not writable:
        return PublishResult()

    batch = _create_backup_batch(
        session.project_id,
        session.manifest.package_root,
        [fp.rel_path for fp in writable],
        kind="publish",
        app_data_dir=app_data_dir,
    )

    published: list[PublishFilePlan] = []
    failed_file: str | None = None
    err_msg: str | None = None

    for fp in writable:
        try:
            atomic_write_bytes_with_retry(
                fp.target_path,
                fp.candidate_bytes,
                replace_fn=replace_fn,
                sleep_fn=sleep_fn,
            )
            published.append(fp)
        except OSError as exc:
            failed_file = fp.rel_path
            err_msg = str(exc)
            break

    result = PublishResult(
        batch_id=batch.batch_id,
        published_files=[fp.rel_path for fp in published],
        published_plans=published,
        failed_file=failed_file,
        error=err_msg,
    )
    if failed_file is None:
        commit_publish_result(session, result)
    return result


def _find_backup_batch(
    project_id: str,
    batch_id: str,
    app_data_dir: Path | None,
) -> BackupBatch | None:
    for batch in list_backup_batches(project_id, app_data_dir=app_data_dir):
        if batch.batch_id == batch_id:
            return batch
    return None


def _read_batch_payloads(
    batch: BackupBatch,
    rel_paths: list[str] | None,
    *,
    validate: bool,
) -> list[tuple[BackupFileEntry, bytes]]:
    chosen = [e for e in batch.files if rel_paths is None or e.rel_path in rel_paths]
    payloads: list[tuple[BackupFileEntry, bytes]] = []
    for entry in chosen:
        bak_path = batch.batch_dir / entry.backup_name
        if not bak_path.exists():
            if validate:
                raise FileNotFoundError(f"Backup file missing: {bak_path}")
            continue
        raw = bak_path.read_bytes()
        if validate:
            if hashlib.sha256(raw).hexdigest() != entry.sha256:
                raise ValueError(f"Backup checksum mismatch for '{entry.rel_path}'.")
            doc = parse_lang_bytes(raw)
            if doc.fatal_error is not None:
                raise ValueError(
                    f"Backup '{entry.rel_path}' contains fatal JSON error: {doc.fatal_error.message}"
                )
        payloads.append((entry, raw))
    return payloads


def _write_batch_payloads(
    session: PackageSession,
    payloads: list[tuple[BackupFileEntry, bytes]],
    io_opts: IoOptions,
) -> list[str]:
    written: list[str] = []
    for entry, raw in payloads:
        target = session.manifest.package_root / entry.rel_path
        atomic_write_bytes_with_retry(
            target,
            raw,
            replace_fn=io_opts.replace_fn,
            sleep_fn=io_opts.sleep_fn,
        )
        written.append(entry.rel_path)
    return written


def rollback_publish_batch(
    session: PackageSession,
    batch_id: str,
    rel_paths: list[str] | None = None,
    app_data_dir: Path | None = None,
    replace_fn: ReplaceFn = os.replace,
    sleep_fn: SleepFn = time.sleep,
) -> list[str]:
    """Revert previously written files from a publish batch while keeping local drafts and review state intact."""
    batch = _find_backup_batch(session.project_id, batch_id, app_data_dir)
    if batch is None:
        return []
    io_opts = IoOptions(app_data_dir=app_data_dir, replace_fn=replace_fn, sleep_fn=sleep_fn)
    payloads = _read_batch_payloads(batch, rel_paths, validate=False)
    reverted = _write_batch_payloads(session, payloads, io_opts)
    if reverted:
        reverted_set = set(reverted)
        _refresh_file_snapshots_from_disk_bytes(
            session,
            [(entry.rel_path, raw) for entry, raw in payloads if entry.rel_path in reverted_set],
        )
    return reverted


def restore_backup(
    session: PackageSession,
    batch_id: str,
    rel_paths: list[str] | None = None,
    discard_local_drafts: bool = False,
    app_data_dir: Path | None = None,
    replace_fn: ReplaceFn = os.replace,
    sleep_fn: SleepFn = time.sleep,
) -> RestoreResult:
    """Validate .bak files, create a pre-restore batch, apply restore atomically, and sync or prepare conflict merge."""
    batch = _find_backup_batch(session.project_id, batch_id, app_data_dir)
    if batch is None:
        raise ValueError(f"Backup batch '{batch_id}' not found.")

    payloads = _read_batch_payloads(batch, rel_paths, validate=True)
    if not payloads:
        return RestoreResult()

    io_opts = IoOptions(app_data_dir=app_data_dir, replace_fn=replace_fn, sleep_fn=sleep_fn)
    pre_batch = _create_backup_batch(
        session.project_id,
        session.manifest.package_root,
        [e.rel_path for e, _ in payloads],
        kind="pre-restore",
        app_data_dir=app_data_dir,
    )

    restored = _write_batch_payloads(session, payloads, io_opts)

    if discard_local_drafts:
        restored_set = set(restored)
        for row in session.rows:
            for lang, cell in row.cells.items():
                eff_rel = cell.source_file or resolve_target_file_for_key(
                    session, lang, row.base_source_file
                )
                if eff_rel in restored_set and cell.is_dirty:
                    cell.revert_to_production(base_text=row.base_text)

    preview = prepare_disk_sync(session)
    if preview.report.blocked_files or preview.report.conflicts:
        return RestoreResult(
            restored_files=restored,
            pre_restore_batch_id=pre_batch.batch_id,
            blocked_files=preview.report.blocked_files,
            sync_preview=preview,
        )

    commit_sync_preview(session, preview)
    return RestoreResult(
        restored_files=restored,
        pre_restore_batch_id=pre_batch.batch_id,
    )

