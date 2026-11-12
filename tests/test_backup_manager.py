import json
from pathlib import Path

from app.core.backup_manager import (
    commit_publish_result,
    delete_backup_batch,
    execute_publish_plan,
    list_backup_batches,
    prepare_publish_plan,
    restore_backup,
    rollback_publish_batch,
)
from app.core.project_manager import discover_manifest, load_package_session


def _write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def test_publish_pipeline_retries_partial_failure_rollback_and_retention(
    tmp_path: Path,
) -> None:
    app_data = tmp_path / "appdata"
    _write_json(app_data / "settings.json", {"backup_retention": 2})

    pkg = tmp_path / "pub-mod"
    _write_json(
        pkg / "module.json",
        {
            "id": "pub-mod",
            "languages": [
                {"lang": "en", "path": "lang/en.json"},
                {"lang": "pt-BR", "path": "lang/pt-BR.json"},
                {"lang": "es", "path": "lang/es.json"},
            ],
        },
    )
    _write_json(pkg / "lang/en.json", {"A": "One", "B": "Two"})
    _write_json(pkg / "lang/pt-BR.json", {"A": "Um", "OLD": "Velha"})
    _write_json(pkg / "lang/es.json", {"A": "Uno"})

    session = load_package_session(discover_manifest(pkg / "module.json"))
    rows = {r.key_path: r for r in session.rows}
    rows["A"].cells["pt-BR"].apply_edit("Um revisto", base_text="One")
    rows["A"].cells["pt-BR"].mark_reviewed()
    rows["B"].cells["pt-BR"].apply_edit("Dois novo", base_text="Two")
    rows["OLD"].cells["pt-BR"].set_marked_for_deletion(True)
    rows["A"].cells["es"].apply_edit("Uno editado", base_text="One")

    plan = prepare_publish_plan(session)
    assert not plan.external_changes
    by_rel = {fp.rel_path: fp for fp in plan.file_plans}
    assert set(by_rel.keys()) == {"lang/pt-BR.json", "lang/es.json"}
    assert "B" in by_rel["lang/pt-BR.json"].unreviewed_dirty_keys
    assert "OLD" in by_rel["lang/pt-BR.json"].deleted_keys

    # Simula PermissionError transitório (2 falhas + sucesso na 3ª tentativa para pt-BR),
    # e falha definitiva (5+ erros) em es.json para testar falha parcial + rollback!
    attempts: dict[str, int] = {}

    def flaky_replace(src: Path, dst: Path) -> None:
        name = dst.name
        attempts[name] = attempts.get(name, 0) + 1
        if name == "pt-BR.json" and attempts[name] <= 2:
            raise PermissionError("OneDrive lock")
        if name == "es.json":
            raise PermissionError("Persistent lock")
        import os

        os.replace(src, dst)

    res = execute_publish_plan(
        session,
        [by_rel["lang/pt-BR.json"], by_rel["lang/es.json"]],
        app_data_dir=app_data,
        replace_fn=flaky_replace,
        sleep_fn=lambda _s: None,
    )
    assert res.published_files == ["lang/pt-BR.json"]
    assert res.failed_file == "lang/es.json"
    assert attempts["pt-BR.json"] == 3
    assert attempts["es.json"] == 5

    # pt-BR gravou no disco, mas como houve falha parcial, sessão preserva rascunhos/review até decisão
    pt_disk = json.loads((pkg / "lang/pt-BR.json").read_text(encoding="utf-8"))
    assert pt_disk == {"A": "Um revisto", "B": "Dois novo"}
    assert rows["A"].cells["pt-BR"].is_dirty is True
    assert rows["A"].cells["pt-BR"].review_status == "reviewed"
    assert rows["A"].cells["es"].is_dirty is True

    # Rollback seletivo do arquivo publicado reverte pt-BR no disco e preserva rascunhos e status "reviewed"
    assert res.batch_id is not None
    reverted = rollback_publish_batch(
        session,
        res.batch_id,
        rel_paths=res.published_files,
        app_data_dir=app_data,
    )
    assert reverted == ["lang/pt-BR.json"]
    pt_rolled = json.loads((pkg / "lang/pt-BR.json").read_text(encoding="utf-8"))
    assert pt_rolled == {"A": "Um", "OLD": "Velha"}
    assert rows["A"].cells["pt-BR"].local_value == "Um revisto"
    assert rows["A"].cells["pt-BR"].review_status == "reviewed"

    # Retenção: criar mais 2 lotes mantendo limite=2 em settings.json
    execute_publish_plan(session, [by_rel["lang/pt-BR.json"]], app_data_dir=app_data)
    res_last = execute_publish_plan(session, [by_rel["lang/pt-BR.json"]], app_data_dir=app_data)
    assert res_last.failed_file is None
    assert rows["A"].cells["pt-BR"].is_dirty is False
    assert rows["A"].cells["pt-BR"].review_status == "reviewed"
    batches = list_backup_batches(session.project_id, app_data_dir=app_data)
    assert len(batches) == 2

    # Também valida commit_publish_result explícito quando usuário mantém envio parcial
    rows["A"].cells["pt-BR"].apply_edit("Um parcial", base_text="One")
    rows["A"].cells["pt-BR"].mark_reviewed()
    plan_partial = prepare_publish_plan(session)
    res_partial = execute_publish_plan(
        session,
        [fp for fp in plan_partial.file_plans if fp.lang in ("pt-BR", "es")],
        app_data_dir=app_data,
        replace_fn=flaky_replace,
        sleep_fn=lambda _s: None,
    )
    assert res_partial.failed_file == "lang/es.json"
    commit_publish_result(session, res_partial)
    assert rows["A"].cells["pt-BR"].is_dirty is False
    assert rows["A"].cells["pt-BR"].review_status == "reviewed"
    assert rows["A"].cells["es"].is_dirty is True

    # Exclusão manual de lote
    delete_backup_batch(session.project_id, batches[0].batch_id, app_data_dir=app_data)
    assert len(list_backup_batches(session.project_id, app_data_dir=app_data)) == 1


def test_restore_backup_creates_pre_restore_and_supports_sync_or_discard(
    tmp_path: Path,
) -> None:
    app_data = tmp_path / "appdata"
    pkg = tmp_path / "restore-mod"
    _write_json(
        pkg / "module.json",
        {
            "id": "restore-mod",
            "languages": [
                {"lang": "en", "path": "lang/en.json"},
                {"lang": "pt-BR", "path": "lang/pt-BR.json"},
            ],
        },
    )
    _write_json(pkg / "lang/en.json", {"A": "One", "B": "Two"})
    _write_json(pkg / "lang/pt-BR.json", {"A": "Um v1", "B": "Dois v1"})

    session = load_package_session(discover_manifest(pkg / "module.json"))
    rows = {r.key_path: r for r in session.rows}
    rows["A"].cells["pt-BR"].apply_edit("Um v2", base_text="One")
    rows["A"].cells["pt-BR"].mark_reviewed()
    plan1 = prepare_publish_plan(session)
    pub1 = execute_publish_plan(session, plan1.file_plans, app_data_dir=app_data)
    assert pub1.batch_id is not None

    # Edita rascunho local não publicado em B
    rows["B"].cells["pt-BR"].apply_edit("Dois rascunho", base_text="Two")

    # Restaura o lote pub1 escolhendo manter/sincronizar rascunhos locais -> cria pre-restore antes
    rest_sync = restore_backup(
        session,
        batch_id=pub1.batch_id,
        discard_local_drafts=False,
        app_data_dir=app_data,
    )
    assert rest_sync.pre_restore_batch_id is not None
    assert json.loads((pkg / "lang/pt-BR.json").read_text(encoding="utf-8")) == {"A": "Um v1", "B": "Dois v1"}
    r_rows = {r.key_path: r for r in session.rows}
    assert r_rows["A"].cells["pt-BR"].review_status == "unreviewed"  # mudou de v2 para v1 -> volta a unreviewed
    assert r_rows["B"].cells["pt-BR"].local_value == "Dois rascunho"  # rascunho preservado

    # Agora restaura o pre-restore escolhendo descartar rascunhos locais
    restore_backup(
        session,
        batch_id=rest_sync.pre_restore_batch_id,
        discard_local_drafts=True,
        app_data_dir=app_data,
    )
    assert json.loads((pkg / "lang/pt-BR.json").read_text(encoding="utf-8")) == {"A": "Um v2", "B": "Dois v1"}
    r_rows2 = {r.key_path: r for r in session.rows}
    assert r_rows2["B"].cells["pt-BR"].local_value == "Dois v1"
    assert r_rows2["B"].cells["pt-BR"].is_dirty is False


def test_mirror_routing_pending_conflicts_and_granular_restore(tmp_path: Path) -> None:
    app_data = tmp_path / "appdata"
    pkg = tmp_path / "multi-mirror"
    _write_json(
        pkg / "module.json",
        {
            "id": "multi-mirror",
            "languages": [
                {"lang": "en", "path": "lang/action-en.json"},
                {"lang": "en", "path": "lang/ui-en.json"},
                {"lang": "pt-BR", "path": "lang/action-pt-BR.json"},
                {"lang": "pt-BR", "path": "lang/ui-pt-BR.json"},
            ],
        },
    )
    _write_json(pkg / "lang/action-en.json", {"ACT.Hit": "Hit", "ACT.Miss": "Miss"})
    _write_json(pkg / "lang/ui-en.json", {"UI.Save": "Save", "UI.Cancel": "Cancel"})
    _write_json(pkg / "lang/action-pt-BR.json", {"ACT.Hit": "Acerto v1"})
    _write_json(pkg / "lang/ui-pt-BR.json", {"UI.Save": "Salvar v1"})

    manifest = discover_manifest(pkg / "module.json")
    session = load_package_session(manifest)

    rows_by_key = {r.key_path: r for r in session.rows}
    rows_by_key["UI.Cancel"].cells["pt-BR"].apply_edit("Cancelar", base_text="Cancel")
    rows_by_key["ACT.Hit"].cells["pt-BR"].apply_edit("Acerto v2", base_text="Hit")

    plan = prepare_publish_plan(session)
    by_rel = {fp.rel_path: fp for fp in plan.file_plans}
    assert "lang/ui-pt-BR.json" in by_rel
    assert "UI.Cancel" in by_rel["lang/ui-pt-BR.json"].edited_keys
    assert "lang/action-pt-BR.json" in by_rel
    assert "ACT.Hit" in by_rel["lang/action-pt-BR.json"].edited_keys

    pub_res = execute_publish_plan(session, plan.file_plans, app_data_dir=app_data)
    assert pub_res.batch_id is not None

    rows_by_key = {r.key_path: r for r in session.rows}
    rows_by_key["ACT.Hit"].cells["pt-BR"].apply_edit("Acerto rascunho v3", base_text="Hit")
    rows_by_key["UI.Cancel"].cells["pt-BR"].apply_edit("Cancelar rascunho v3", base_text="Cancel")

    # Restaura apenas action-pt-BR.json descartando rascunho -> ui-pt-BR.json mantém rascunho!
    rest_one = restore_backup(
        session,
        pub_res.batch_id,
        rel_paths=["lang/action-pt-BR.json"],
        discard_local_drafts=True,
        app_data_dir=app_data,
    )
    assert rest_one.restored_files == ["lang/action-pt-BR.json"]
    rows_after = {r.key_path: r for r in session.rows}
    assert rows_after["ACT.Hit"].cells["pt-BR"].local_value == "Acerto v1"
    assert rows_after["ACT.Hit"].cells["pt-BR"].is_dirty is False
    assert rows_after["UI.Cancel"].cells["pt-BR"].local_value == "Cancelar rascunho v3"
    assert rows_after["UI.Cancel"].cells["pt-BR"].is_dirty is True

    # Restaura ui-pt-BR.json mantendo rascunho em conflito -> devolve sync_preview sem auto-commit
    rest_keep = restore_backup(
        session,
        pub_res.batch_id,
        rel_paths=["lang/ui-pt-BR.json"],
        discard_local_drafts=False,
        app_data_dir=app_data,
    )
    assert rest_keep.sync_preview is not None
    assert any(c.key_path == "UI.Cancel" for c in rest_keep.sync_preview.report.conflicts)

    # Conflito de sincronização pendente bloqueia publicação do arquivo
    session.pending_conflict_keys = {("UI.Cancel", "pt-BR")}
    blocked_plan = prepare_publish_plan(session)
    blocked_rels = {fp.rel_path: fp for fp in blocked_plan.file_plans}
    assert blocked_rels["lang/ui-pt-BR.json"].is_blocked is True


