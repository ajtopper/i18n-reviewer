from __future__ import annotations

import os
from pathlib import Path
import sys
import tempfile
from typing import TextIO

from PySide6.QtWidgets import QApplication

from app.core.spell_paths import resolve_sentinel_word
from app.ui.main_window import MainWindow

_SELF_TEST_SPELLS: tuple[tuple[str, str], ...] = (
    ("en", "en_US"),
    ("pt-BR", "pt_BR"),
    ("es", "es_ES"),
    ("fr", "fr_FR"),
    ("de", "de_DE"),
)


def _emit(stream: TextIO | None, line: str) -> None:
    """Safely write diagnostic output even under --windowed or cp1252 redirected streams."""
    if stream is None:
        return
    try:
        stream.write(f"{line}\n")
    except UnicodeEncodeError:
        enc = getattr(stream, "encoding", None) or "ascii"
        safe = line.encode(enc, errors="replace").decode(enc, errors="replace")
        stream.write(f"{safe}\n")
    stream.flush()


def run_self_test(app_data_dir: Path | None = None) -> int:
    """Initialize Qt offscreen, MainWindow, and Hunspell dictionaries using sentinel checks."""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    try:
        app = QApplication.instance()
        if not isinstance(app, QApplication):
            app = QApplication([sys.argv[0] if sys.argv else "i18n-reviewer", "--self-test"])
    except Exception as exc:  # pragma: no cover - defensive GUI bootstrap guard
        _emit(sys.stderr, f"[self-test] FAIL: failed to initialize QApplication: {exc}")
        return 2

    def _check_in_dir(target_dir: Path) -> int:
        try:
            win = MainWindow(app_data_dir=target_dir)
        except Exception as exc:
            _emit(sys.stderr, f"[self-test] FAIL: failed to initialize MainWindow: {exc}")
            return 2
        try:
            failures: list[str] = []
            for ui_lang, enchant_tag in _SELF_TEST_SPELLS:
                status = win.spell_service.status_for(ui_lang)
                sentinel = resolve_sentinel_word(enchant_tag, win.spell_service.effective_hunspell_dir) or "a"
                available = win.spell_service.is_available(ui_lang)
                sentinel_ok = available and win.spell_service.check(ui_lang, sentinel)
                if not available or not sentinel_ok:
                    failures.append(
                        f"{ui_lang} ({enchant_tag}): available={available}, "
                        f"sentinel='{sentinel}' ok={sentinel_ok}, msg={status.message}"
                    )
                else:
                    _emit(sys.stdout, f"[self-test] OK {ui_lang} ({enchant_tag}) sentinel='{sentinel}'")
            if failures:
                for item in failures:
                    _emit(sys.stderr, f"[self-test] FAIL {item}")
                return 1
            return 0
        finally:
            win.close()

    if app_data_dir is not None:
        app_data_dir.mkdir(parents=True, exist_ok=True)
        return _check_in_dir(app_data_dir)

    with tempfile.TemporaryDirectory(prefix="i18n_reviewer_selftest_") as tmp_dir:
        return _check_in_dir(Path(tmp_dir))


def main(argv: list[str] | None = None) -> int:
    """Launch the GUI application or run headless --self-test verification."""
    args = argv if argv is not None else sys.argv[1:]
    if "--self-test" in args:
        return run_self_test()

    app = QApplication.instance()
    if not isinstance(app, QApplication):
        app = QApplication(sys.argv)
    win = MainWindow()
    positional = [a for a in args if not a.startswith("-")]
    if positional:
        manifest_path = Path(positional[0])
        if manifest_path.exists():
            win.open_package_manifest(manifest_path)
    win.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
