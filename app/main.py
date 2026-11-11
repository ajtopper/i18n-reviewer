from __future__ import annotations

from pathlib import Path
import sys

from PySide6.QtWidgets import QApplication

from app.ui.main_window import MainWindow


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    app = QApplication(sys.argv)
    win = MainWindow()
    if args:
        manifest_path = Path(args[0])
        if manifest_path.exists():
            win.open_package_manifest(manifest_path)
    win.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())

