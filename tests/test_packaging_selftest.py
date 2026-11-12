from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
FROZEN_DIR = REPO_ROOT / "dist" / "i18n-reviewer"
FROZEN_EXE = FROZEN_DIR / "i18n-reviewer.exe"


def test_main_self_test_mode_validates_dictionaries_and_handles_failures(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app import main as app_main

    monkeypatch.delenv("QT_QPA_PLATFORM", raising=False)

    # Happy path in --self-test mode should initialize Qt offscreen and verify all 4 languages
    rc = app_main.run_self_test(app_data_dir=tmp_path / "selftest_ok")
    assert rc == 0
    assert os.environ.get("QT_QPA_PLATFORM") == "offscreen"

    # --windowed Windows GUIs may have None stdout/stderr; _emit and run_self_test must not crash
    monkeypatch.setattr(sys, "stdout", None)
    monkeypatch.setattr(sys, "stderr", None)
    assert app_main.run_self_test(app_data_dir=tmp_path / "selftest_null_streams") == 0

    # Simulated dictionary/sentinel failure must return non-zero exit code
    monkeypatch.setattr(
        "app.core.spell_service.SpellService.is_available",
        lambda _self, lang: lang != "de",
    )
    assert app_main.run_self_test(app_data_dir=tmp_path / "selftest_fail") != 0

    # MainWindow bootstrap exception during self-test must return non-zero instead of raising
    monkeypatch.setattr(
        "app.main.MainWindow",
        lambda **_kw: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    assert app_main.run_self_test(app_data_dir=tmp_path / "selftest_exc") == 2


def test_packaging_manifests_spec_and_licenses_are_present() -> None:
    req = (REPO_ROOT / "requirements.txt").read_text(encoding="utf-8")
    req_dev = (REPO_ROOT / "requirements-dev.txt").read_text(encoding="utf-8")
    for pin in ("PySide6-Essentials==6.12.0", "shiboken6==6.12.0", "pyenchant==3.3.0"):
        assert pin in req
    for pin in ("pyinstaller==6.22.3", "pyinstaller-hooks-contrib==2026.10", "pytest", "pytest-qt"):
        assert pin in req_dev

    spec_path = REPO_ROOT / "spec" / "build.spec"
    assert spec_path.exists()
    spec_text = spec_path.read_text(encoding="utf-8")
    assert "module_collection_mode" in spec_text
    assert "'enchant': 'py'" in spec_text or '"enchant": "py"' in spec_text
    for excluded_qt in ("QtWebEngine", "QtQml", "QtQuick", "Qt3D", "QtMultimedia", "QtPdf"):
        assert excluded_qt in spec_text

    licenses_dir = REPO_ROOT / "licenses"
    for fname in ("THIRD_PARTY_NOTICES.md", "LGPL-2.1.txt", "LGPL-3.0.txt", "MPL-2.0.txt", "GPL-2.0.txt", "GPL-3.0.txt"):
        fpath = licenses_dir / fname
        assert fpath.exists(), f"Missing license file: {fpath}"
        assert fpath.stat().st_size > 100

    assert (REPO_ROOT / "scripts" / "package_windows.ps1").exists()
    assert (REPO_ROOT / "installer" / "i18n-reviewer.iss").exists()


@pytest.mark.skipif(
    not FROZEN_EXE.exists() and not os.environ.get("I18N_REQUIRE_FROZEN"),
    reason="Frozen build not present; run scripts/package_windows.ps1 or set I18N_REQUIRE_FROZEN=1",
)
def test_frozen_executable_and_non_ascii_path_self_test(tmp_path: Path) -> None:
    assert FROZEN_EXE.exists(), f"Expected PyInstaller executable at {FROZEN_EXE}"

    internal_dir = FROZEN_DIR / "_internal"
    root_for_inspect = internal_dir if internal_dir.exists() else FROZEN_DIR
    all_names_lower = {p.name.lower() for p in root_for_inspect.rglob("*") if p.is_file()}

    # Pruned libraries must not be bundled
    for forbidden_prefix in ("qt6webengine", "qt6quick", "qt6qml", "qt6pdf", "qt6multimedia", "nuspell", "libicu", "libreadline"):
        assert not any(n.startswith(forbidden_prefix) for n in all_names_lower), f"Unexpected bundled artifact: {forbidden_prefix}"

    # Required enchant + hunspell + 5 dictionaries + licenses must be bundled
    for required_file in (
        "libenchant-2.dll",
        "enchant_hunspell.dll",
        "libhunspell-1.7-0.dll",
        "en_us.aff",
        "en_us.dic",
        "pt_br.aff",
        "pt_br.dic",
        "es_es.aff",
        "es_es.dic",
        "fr_fr.aff",
        "fr_fr.dic",
        "de_de.aff",
        "de_de.dic",
        "third_party_notices.md",
    ):
        assert required_file in all_names_lower, f"Missing required bundled file: {required_file}"

    # Normal path --self-test
    res_ok = subprocess.run([str(FROZEN_EXE), "--self-test"], capture_output=True, text=True, timeout=60)
    assert res_ok.returncode == 0, f"stdout={res_ok.stdout}\nstderr={res_ok.stderr}"

    # Copied to accented / non-ASCII directory path + non-ASCII APPDATA
    accented_root = tmp_path / "ação diretório çé"
    accented_bundle = accented_root / "i18n-reviewer"
    shutil.copytree(FROZEN_DIR, accented_bundle)
    env = os.environ.copy()
    non_ascii_appdata = tmp_path / "dados usuário ção"
    env["APPDATA"] = str(non_ascii_appdata)
    res_non_ascii = subprocess.run(
        [str(accented_bundle / "i18n-reviewer.exe"), "--self-test"],
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )
    assert res_non_ascii.returncode == 0, f"stdout={res_non_ascii.stdout}\nstderr={res_non_ascii.stderr}"
