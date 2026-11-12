import json
from pathlib import Path
import shutil

import pytest

from app.core.project_manager import (
    CellKind,
    PackageNotFoundError,
    UnsupportedProjectVersionError,
    clear_recovery_draft,
    discover_manifest,
    has_recovery_draft,
    load_package_session,
    load_project_file,
    save_project_file,
    write_recovery_draft,
)


def _write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def test_discover_manifest_handles_base_http_escape_case_conditionals_and_babele(
    tmp_path: Path,
) -> None:
    pkg = tmp_path / "my-mod"
    _write_json(
        pkg / "module.json",
        {
            "id": "my-mod",
            "languages": [
                {"lang": "pt-br", "name": "Português", "path": "lang/pt-br.json"},
                {"lang": "en", "name": "English", "path": "lang/en.json"},
                {"lang": "es", "name": "Español", "path": "lang/es.json", "system": "dnd5e"},
                {"lang": "fr", "name": "Remote", "path": "https://example.com/fr.json"},
                {"lang": "de", "name": "Bad", "path": "../outside.json"},
            ],
        },
    )
    _write_json(pkg / "lang/en.json", {"A": "One"})
    _write_json(pkg / "lang/pt-br.json", {"A": "Um"})
    _write_json(pkg / "lang/es.json", {"A": "Uno"})
    # Arquivo do Babele fora de languages[] deve ser ignorado
    _write_json(pkg / "lang/pt-br/compendium/dnd5e.spells.json", {"Fireball": "Bola de Fogo"})

    info = discover_manifest(pkg / "module.json")

    assert info.manifest_type == "module"
    assert info.package_id == "my-mod"
    assert info.default_base_lang == "en"

    by_lang = {entry.lang: entry for entry in info.entries}
    assert by_lang["en"].editable is True
    assert by_lang["pt-br"].editable is True
    assert by_lang["es"].conditional == "system: dnd5e"
    assert by_lang["fr"].is_http is True
    assert by_lang["fr"].editable is False
    assert by_lang["de"].editable is False

    kinds = {w.kind for w in info.warnings}
    assert "non_canonical_bcp47" in kinds
    assert "remote_http" in kinds
    assert "path_escape" in kinds
    assert all("compendium" not in e.path for e in info.entries)


def test_load_package_session_unifies_multifile_cldr_plurals_and_cell_kinds(
    tmp_path: Path,
) -> None:
    pkg = tmp_path / "sys-mod"
    _write_json(
        pkg / "system.json",
        {
            "id": "sys-mod",
            "languages": [
                {"lang": "en", "name": "English Main", "path": "lang/en.json"},
                {"lang": "en", "name": "English Extra", "path": "lang/extra-en.json"},
                {"lang": "pt-BR", "name": "PT1", "path": "lang/pt1.json"},
                {"lang": "pt-BR", "name": "PT2", "path": "lang/pt2.json"},
                {"lang": "es", "name": "ES", "path": "lang/es.json"},
            ],
        },
    )
    _write_json(
        pkg / "lang/en.json",
        {
            "UI": {"Title": "Title", "Empty": "Empty", "Same": "OK", "Count": "Count"},
            "Points": {"one": "{n} pt", "other": "{n} pts"},
            "Other": {"one": "{n} item", "other": "{n} items"},
            "Conflict": {"Sub": "Leaf in base"},
        },
    )
    _write_json(pkg / "lang/extra-en.json", {"EXTRA": {"Note": "Extra note"}})
    _write_json(
        pkg / "lang/pt1.json",
        {
            "UI": {"Title": "Título antigo", "Empty": "", "Same": "OK", "Count": 10},
            "Points": {"one": "{n} pt", "many": "{n} pontos", "other": "{n} pontos"},
            "Other": {"one": "{n} item", "other": "{n} itens"},
            "Conflict": "String no destino",
            "ORPHAN": {"Legacy": "Antiga"},
        },
    )
    _write_json(
        pkg / "lang/pt2.json",
        {
            "UI": {"Title": "Título novo"},
        },
    )
    _write_json(pkg / "lang/es.json", {"UI": {"Title": "Título"}})

    # Desabilita 'es' opcionalmente para validar filtro de entradas na carga
    info = discover_manifest(pkg / "system.json")
    enabled = [e for e in info.entries if e.lang != "es"]
    session = load_package_session(info, base_lang="en", selected_entries=enabled)

    assert session.target_langs == ["pt-BR"]
    rows = {r.key_path: r for r in session.rows}

    # Multi-arquivo: último vence em colisão e registra colisão
    assert rows["UI.Title"].cells["pt-BR"].prod_value == "Título novo"
    assert rows["UI.Title"].cells["pt-BR"].source_file == "lang/pt2.json"
    assert any(w.kind == "multi_file_collision" and w.key_path == "UI.Title" for w in session.warnings)

    # Diferenciação de estados
    assert rows["EXTRA.Note"].cells["pt-BR"].kind == CellKind.MISSING
    assert rows["UI.Empty"].cells["pt-BR"].kind == CellKind.EMPTY
    assert rows["UI.Same"].cells["pt-BR"].kind == CellKind.SAME_AS_BASE
    assert rows["UI.Count"].cells["pt-BR"].kind == CellKind.NON_STRING
    assert rows["ORPHAN.Legacy"].cells["pt-BR"].kind == CellKind.ORPHAN

    # Conflito estrutural (objeto na base vs string no destino)
    assert rows["Conflict.Sub"].cells["pt-BR"].kind == CellKind.STRUCTURAL_CONFLICT
    assert rows["Conflict"].cells["pt-BR"].kind == CellKind.STRUCTURAL_CONFLICT

    # Plurais CLDR: pt-BR tem .many válido (NÃO é órfã), e sugere Other.many ausente
    assert rows["Points.many"].cells["pt-BR"].kind == CellKind.TRANSLATED
    assert rows["Other.many"].cells["pt-BR"].kind == CellKind.MISSING
    assert rows["Other.many"].base_text == "{n} items"


def test_load_package_session_supports_external_base_and_isolates_fatal_file(
    tmp_path: Path,
) -> None:
    pkg = tmp_path / "pt-only-mod"
    _write_json(
        pkg / "module.json",
        {
            "id": "pt-only-mod",
            "languages": [
                {"lang": "pt-BR", "path": "lang/pt-BR.json"},
                {"lang": "es", "path": "lang/es.json"},
            ],
        },
    )
    _write_json(pkg / "lang/pt-BR.json", {"HELLO": "Olá"})
    # es.json tem folha antes de ramo (fatal para o Foundry)
    (pkg / "lang/es.json").write_text('{"HELLO": "Hola", "HELLO.Sub": "Bad"}\n', encoding="utf-8")

    ext_en = tmp_path / "external-en.json"
    _write_json(ext_en, {"HELLO": "Hello", "BYE": "Bye"})

    info = discover_manifest(pkg / "module.json")
    session = load_package_session(info, base_lang="en", base_external_path=ext_en)

    assert session.base_lang == "en"
    assert session.target_langs == ["pt-BR", "es"]
    rows = {r.key_path: r for r in session.rows}
    assert rows["HELLO"].cells["pt-BR"].kind == CellKind.TRANSLATED
    assert rows["BYE"].cells["pt-BR"].kind == CellKind.MISSING
    assert rows["HELLO"].cells["es"].readonly is True
    assert any(w.kind == "fatal_file" and w.lang == "es" for w in session.warnings)


def test_cldr_plurals_are_isolated_per_target_language(tmp_path: Path) -> None:
    pkg = tmp_path / "cldr-mod"
    _write_json(
        pkg / "module.json",
        {
            "id": "cldr-mod",
            "languages": [
                {"lang": "en", "path": "lang/en.json"},
                {"lang": "pt-BR", "path": "lang/pt-BR.json"},
                {"lang": "de", "path": "lang/de.json"},
            ],
        },
    )
    _write_json(pkg / "lang/en.json", {"Pts": {"one": "{n} pt", "other": "{n} pts"}})
    _write_json(pkg / "lang/pt-BR.json", {"Pts": {"one": "{n} ponto", "other": "{n} pontos"}})
    _write_json(
        pkg / "lang/de.json",
        {"Pts": {"one": "{n} Pkt", "many": "Espúrio em de", "other": "{n} Pkte"}},
    )

    info = discover_manifest(pkg / "module.json")
    session = load_package_session(info)
    rows = {r.key_path: r for r in session.rows}

    # .many é sugerido como MISSING para pt-BR, mas NÃO se aplica a 'de'; como 'de' tem .many espúrio, vira ORPHAN!
    assert rows["Pts.many"].cells["pt-BR"].kind == CellKind.MISSING
    assert rows["Pts.many"].cells["de"].kind == CellKind.ORPHAN

    # Caso inverso: quando 'de' não tem .many, fica NOT_APPLICABLE (não é MISSING!)
    _write_json(pkg / "lang/de.json", {"Pts": {"one": "{n} Pkt", "other": "{n} Pkte"}})
    session2 = load_package_session(discover_manifest(pkg / "module.json"))
    rows2 = {r.key_path: r for r in session2.rows}
    assert rows2["Pts.many"].cells["pt-BR"].kind == CellKind.MISSING
    assert rows2["Pts.many"].cells["de"].kind == CellKind.NOT_APPLICABLE


def test_cell_state_machine_transitions_edit_review_revert_and_orphan_deletion() -> None:
    from app.core.project_manager import CellData

    # 1) Editar célula existente torna is_dirty=True e rebaixa review_status para unreviewed
    cell = CellData(prod_value="Olá", local_value="Olá", kind=CellKind.TRANSLATED)
    assert cell.is_dirty is False
    assert cell.mark_reviewed() is True
    assert cell.review_status == "reviewed"

    assert cell.apply_edit("Oi", base_text="Hello") is True
    assert cell.is_dirty is True
    assert cell.review_status == "unreviewed"

    # Editar de volta ao valor idêntico ao prod_value limpa is_dirty automaticamente
    assert cell.apply_edit("Olá", base_text="Hello") is True
    assert cell.is_dirty is False

    # 2) Editar célula MISSING preenche local_value e sai de MISSING; cancelar vazio não cria chave
    missing = CellData(prod_value=None, local_value=None, kind=CellKind.MISSING)
    assert missing.is_missing is True
    assert missing.mark_reviewed() is False
    assert missing.apply_edit("", base_text="Bye") is False
    assert missing.apply_edit("Tchau", base_text="Bye") is True
    assert missing.is_missing is False
    assert missing.is_dirty is True
    assert missing.kind == CellKind.TRANSLATED
    assert missing.mark_reviewed() is True
    assert missing.review_status == "reviewed"

    # Reverter restaura para MISSING
    missing.revert_to_production(base_text="Bye")
    assert missing.is_missing is True
    assert missing.is_dirty is False
    assert missing.kind == CellKind.MISSING

    # 3) Remoção de órfã torna is_dirty=True e não permite revisão enquanto marcada
    orphan = CellData(prod_value="Antiga", local_value="Antiga", kind=CellKind.ORPHAN)
    assert orphan.set_marked_for_deletion(True) is True
    assert orphan.is_dirty is True
    assert orphan.mark_reviewed() is False
    assert orphan.set_marked_for_deletion(False) is True
    assert orphan.is_dirty is False

    # 4) Estado stale e bloqueios de edição/revisão
    stale = CellData(
        prod_value="Texto",
        local_value="Texto",
        kind=CellKind.TRANSLATED,
        review_status="stale",
        previous_base="Old base",
    )
    assert stale.is_pending is True
    assert stale.mark_reviewed() is True
    assert stale.review_status == "reviewed"
    assert stale.previous_base is None

    stale.review_status = "stale"
    stale.previous_base = "Old base"
    assert stale.apply_edit("Texto ajustado", base_text="New base") is True
    assert stale.review_status == "unreviewed"

    for locked_kind in (CellKind.NON_STRING, CellKind.STRUCTURAL_CONFLICT, CellKind.NOT_APPLICABLE):
        locked = CellData(prod_value="x", local_value="x", kind=locked_kind)
        assert locked.can_edit() is False
        assert locked.apply_edit("y", base_text="b") is False
        assert locked.mark_reviewed() is False

    ro = CellData(prod_value="x", local_value="x", kind=CellKind.TRANSLATED, readonly=True)
    assert ro.can_edit() is False
    assert ro.apply_edit("y", base_text="b") is False
    assert ro.mark_reviewed() is False


def test_save_and_load_i18nproj_portability_versioning_and_recovery(tmp_path: Path) -> None:
    app_data = tmp_path / "appdata"
    workspace = tmp_path / "ws1"
    pkg = workspace / "my-mod"
    _write_json(
        pkg / "module.json",
        {
            "id": "my-mod",
            "languages": [
                {"lang": "en", "path": "lang/en.json"},
                {"lang": "pt-BR", "path": "lang/pt-BR.json"},
            ],
        },
    )
    _write_json(pkg / "lang/en.json", {"A": "One", "B": "Two"})
    _write_json(pkg / "lang/pt-BR.json", {"A": "Um", "OLD": "Velha"})

    info = discover_manifest(pkg / "module.json")
    session = load_package_session(info)
    rows = {r.key_path: r for r in session.rows}
    rows["A"].cells["pt-BR"].mark_reviewed()
    rows["B"].cells["pt-BR"].apply_edit("Dois", base_text="Two")
    rows["OLD"].cells["pt-BR"].set_marked_for_deletion(True)

    proj_path = workspace / "projects" / "my-mod.i18nproj"
    save_project_file(session, proj_path, app_data_dir=app_data)

    # Arquivo .i18nproj gravado com schema_version=1 e snapshots SHA-256
    raw_proj = json.loads(proj_path.read_text(encoding="utf-8"))
    assert raw_proj["schema_version"] == 1
    assert raw_proj["project_id"] == session.project_id
    assert raw_proj["drafts"]["edits"]["pt-BR"] == {"B": "Dois"}
    assert raw_proj["drafts"]["deletions"]["pt-BR"] == ["OLD"]
    assert raw_proj["review_state"]["pt-BR"]["A"]["status"] == "reviewed"

    # Portabilidade: move workspace inteiro para ws2 -> caminho relativo continua resolvendo!
    ws2 = tmp_path / "ws2"
    shutil.move(str(workspace), str(ws2))
    moved_proj = ws2 / "projects" / "my-mod.i18nproj"
    reopened = load_project_file(moved_proj)
    r_rows = {r.key_path: r for r in reopened.session.rows}
    assert r_rows["A"].cells["pt-BR"].review_status == "reviewed"
    assert r_rows["B"].cells["pt-BR"].local_value == "Dois"
    assert r_rows["B"].cells["pt-BR"].is_dirty is True
    assert r_rows["OLD"].cells["pt-BR"].marked_for_deletion is True

    # Se mover apenas o .i18nproj e apagar ws2/my-mod original, pede relocalização e aceita relocated_root
    relocated_pkg = tmp_path / "relocated-pkg"
    shutil.move(str(ws2 / "my-mod"), str(relocated_pkg))
    with pytest.raises(PackageNotFoundError):
        load_project_file(moved_proj)
    reopened_reloc = load_project_file(moved_proj, relocated_root=relocated_pkg)
    assert reopened_reloc.session.manifest.package_root == relocated_pkg.resolve()

    # Migração de versão antiga (0 -> 1) cria backup do .i18nproj antes
    old_data = json.loads(moved_proj.read_text(encoding="utf-8"))
    old_data["schema_version"] = 0
    moved_proj.write_text(json.dumps(old_data), encoding="utf-8")
    migrated = load_project_file(moved_proj, relocated_root=relocated_pkg)
    assert migrated.migrated_from == 0
    assert (moved_proj.parent / f"{moved_proj.name}.v0.bak").exists()

    # Versão futura (> 1) é recusada
    future_data = json.loads(moved_proj.read_text(encoding="utf-8"))
    future_data["schema_version"] = 99
    moved_proj.write_text(json.dumps(future_data), encoding="utf-8")
    with pytest.raises(UnsupportedProjectVersionError):
        load_project_file(moved_proj, relocated_root=relocated_pkg)

    # Crash recovery: grava rascunho em appdata, detecta e restaura; salvar ou limpar remove recovery
    moved_proj.write_text(json.dumps(old_data | {"schema_version": 1}), encoding="utf-8")
    reopened_reloc.session.rows[0].cells["pt-BR"].apply_edit("Um rascunho crash", base_text="One")
    write_recovery_draft(reopened_reloc.session, app_data_dir=app_data)
    assert has_recovery_draft(reopened_reloc.session.project_id, app_data_dir=app_data) is True
    recovered = load_project_file(moved_proj, relocated_root=relocated_pkg, apply_recovery_dir=app_data)
    assert {r.key_path: r for r in recovered.session.rows}["A"].cells["pt-BR"].local_value == "Um rascunho crash"
    clear_recovery_draft(reopened_reloc.session.project_id, app_data_dir=app_data)
    assert has_recovery_draft(reopened_reloc.session.project_id, app_data_dir=app_data) is False


def test_three_way_merge_stale_transition_and_invalid_disk_blocking(tmp_path: Path) -> None:
    from app.core.project_manager import check_external_disk_changes, synchronize_session_with_disk

    pkg = tmp_path / "sync-mod"
    _write_json(
        pkg / "module.json",
        {
            "id": "sync-mod",
            "languages": [
                {"lang": "en", "path": "lang/en.json"},
                {"lang": "pt-BR", "path": "lang/pt-BR.json"},
            ],
        },
    )
    _write_json(
        pkg / "lang/en.json",
        {
            "K_AUTO": "Auto",
            "K_CONV": "Converge",
            "K_CONF": "Conflict",
            "K_DEL_CONF": "Deleted remotely",
            "K_BASE_CHG": "Old English",
            "K_UNREV": "Old Unrev",
        },
    )
    _write_json(
        pkg / "lang/pt-BR.json",
        {
            "K_AUTO": "Auto prod",
            "K_CONV": "Conv prod",
            "K_CONF": "Conf prod",
            "K_DEL_CONF": "Del prod",
            "K_BASE_CHG": "Inglês antigo",
            "K_UNREV": "Não rev",
        },
    )

    session = load_package_session(discover_manifest(pkg / "module.json"))
    rows = {r.key_path: r for r in session.rows}
    rows["K_AUTO"].cells["pt-BR"].mark_reviewed()
    rows["K_BASE_CHG"].cells["pt-BR"].mark_reviewed()
    rows["K_CONV"].cells["pt-BR"].apply_edit("Mesmo do disco", base_text="Converge")
    rows["K_CONF"].cells["pt-BR"].apply_edit("Minha edição", base_text="Conflict")
    rows["K_DEL_CONF"].cells["pt-BR"].apply_edit("Editada local", base_text="Deleted remotely")

    proj_path = tmp_path / "sync-mod.i18nproj"
    save_project_file(session, proj_path)

    # Simula git pull externo nos arquivos de idioma
    _write_json(
        pkg / "lang/en.json",
        {
            "K_AUTO": "Auto",
            "K_CONV": "Converge",
            "K_CONF": "Conflict",
            "K_DEL_CONF": "Deleted remotely",
            "K_BASE_CHG": "New English",
            "K_UNREV": "New Unrev",
        },
    )
    _write_json(
        pkg / "lang/pt-BR.json",
        {
            "K_AUTO": "Auto disco",
            "K_CONV": "Mesmo do disco",
            "K_CONF": "Edição do disco",
            "K_BASE_CHG": "Inglês antigo",
            "K_UNREV": "Não rev",
        },
    )

    assert set(check_external_disk_changes(session)) == {"lang/en.json", "lang/pt-BR.json"}
    reopened = load_project_file(proj_path)
    rep = reopened.sync_report
    assert set(rep.changed_files) == {"lang/en.json", "lang/pt-BR.json"}
    assert rep.auto_absorbed_count >= 1
    assert rep.converged_count == 1
    assert rep.stale_marked_count == 1

    m_rows = {r.key_path: r for r in reopened.session.rows}
    assert m_rows["K_AUTO"].cells["pt-BR"].local_value == "Auto disco"
    assert m_rows["K_AUTO"].cells["pt-BR"].review_status == "unreviewed"
    assert m_rows["K_CONV"].cells["pt-BR"].is_dirty is False
    assert m_rows["K_BASE_CHG"].cells["pt-BR"].review_status == "stale"
    assert m_rows["K_BASE_CHG"].cells["pt-BR"].previous_base == "Old English"
    assert m_rows["K_UNREV"].cells["pt-BR"].review_status == "unreviewed"

    conflicts = {c.key_path: c for c in rep.conflicts}
    assert set(conflicts.keys()) == {"K_CONF", "K_DEL_CONF"}
    assert conflicts["K_CONF"].snapshot_value == "Conf prod"
    assert conflicts["K_CONF"].disk_value == "Edição do disco"
    assert conflicts["K_CONF"].local_value == "Minha edição"
    assert conflicts["K_DEL_CONF"].disk_value is None

    # Arquivo inválido no disco bloqueia sincronização ativa
    (pkg / "lang/pt-BR.json").write_text("{broken json", encoding="utf-8")
    blocked_rep = synchronize_session_with_disk(session)
    assert "lang/pt-BR.json" in blocked_rep.blocked_files


def test_ignored_warnings_and_custom_enrichers_persist_in_i18nproj(tmp_path: Path) -> None:
    from app.core.validator import CustomEnricherRule, IgnoredWarning, compute_value_hash

    app_data = tmp_path / "appdata"
    pkg = tmp_path / "rules-mod"
    _write_json(
        pkg / "module.json",
        {
            "id": "rules-mod",
            "languages": [
                {"lang": "en", "path": "lang/en.json"},
                {"lang": "pt-BR", "path": "lang/pt-BR.json"},
            ],
        },
    )
    _write_json(pkg / "lang/en.json", {"K1": "Hi {name}", "K2": "Run %MACRO%"})
    _write_json(pkg / "lang/pt-BR.json", {"K1": "Oi mundo", "K2": "Executar %MACRO%"})

    session = load_package_session(discover_manifest(pkg / "module.json"))
    session.custom_enrichers = [CustomEnricherRule(name="PercMacro", pattern=r"%[A-Z]+%")]
    session.ignored_warnings = [
        IgnoredWarning(
            key_path="K1",
            lang="pt-BR",
            rule_id="placeholder_mismatch",
            value_hash=compute_value_hash("Oi mundo"),
            reason="Texto simplificado",
        )
    ]

    proj_file = tmp_path / "rules.i18nproj"
    save_project_file(session, proj_file, app_data_dir=app_data)

    reopened = load_project_file(proj_file)
    assert reopened.session.custom_enrichers == session.custom_enrichers
    assert reopened.session.ignored_warnings == session.ignored_warnings





