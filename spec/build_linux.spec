# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller specification for i18n Reviewer (Linux x86_64 --onedir for AppImage)."""

from __future__ import annotations

import glob
import os

PROJECT_ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))

_EXCLUDED_QT_MODULES = (
    "webengine",
    "webchannel",
    "qml",
    "quick",
    "3d",
    "multimedia",
    "pdf",
    "designer",
    "help",
    "positioning",
    "sensors",
    "serialport",
    "spatialaudio",
)
_EXCLUDED_QT_BIN_PREFIXES = tuple(f"libqt6{m}" for m in _EXCLUDED_QT_MODULES)
_EXCLUDED_QT_DATA_PREFIXES = tuple(f"qt{m}" for m in _EXCLUDED_QT_MODULES)


def _norm_dest(entry: tuple[str, ...]) -> str:
    return entry[0].replace("\\", "/").lower()


def _keep_binary(entry: tuple[str, ...]) -> bool:
    dest = _norm_dest(entry)
    fname = dest.rsplit("/", 1)[-1]
    return not fname.startswith(_EXCLUDED_QT_BIN_PREFIXES)


def _keep_data(entry: tuple[str, ...]) -> bool:
    dest = _norm_dest(entry)
    fname = dest.rsplit("/", 1)[-1]
    return not fname.startswith(_EXCLUDED_QT_DATA_PREFIXES)


def _collect_linux_enchant_binaries() -> list[tuple[str, str]]:
    """Bundle system libenchant-2, libhunspell, and enchant_hunspell.so for AppImage portability."""
    bins: list[tuple[str, str]] = []
    seen_targets: set[tuple[str, str]] = set()

    def _add(src: str, dest_dir: str) -> None:
        real = os.path.realpath(src)
        key = (os.path.basename(src), dest_dir)
        if os.path.isfile(real) and key not in seen_targets:
            seen_targets.add(key)
            bins.append((real, dest_dir))

    lib_dirs = (
        "/usr/lib/x86_64-linux-gnu",
        "/lib/x86_64-linux-gnu",
        "/usr/lib64",
        "/usr/lib",
    )
    for lib_dir in lib_dirs:
        if not os.path.isdir(lib_dir):
            continue
        for pat in ("libenchant-2.so*", "libhunspell-*.so*"):
            for match in sorted(glob.glob(os.path.join(lib_dir, pat))):
                _add(match, ".")
        for mod in sorted(glob.glob(os.path.join(lib_dir, "enchant-2", "enchant_hunspell.so"))):
            _add(mod, os.path.join("enchant_prefix", "lib", "enchant-2"))

    return bins


_EXTRA_DATAS = [
    (os.path.join(PROJECT_ROOT, "resources", "hunspell"), os.path.join("resources", "hunspell")),
    (os.path.join(PROJECT_ROOT, "resources", "icons"), os.path.join("resources", "icons")),
    (os.path.join(PROJECT_ROOT, "licenses"), "licenses"),
]
_SYSTEM_ORDERING = "/etc/enchant-2/enchant.ordering"
if os.path.isfile(_SYSTEM_ORDERING):
    _EXTRA_DATAS.append((_SYSTEM_ORDERING, os.path.join("enchant_prefix", "share", "enchant")))

a = Analysis(
    [os.path.join(PROJECT_ROOT, "app", "main.py")],
    pathex=[PROJECT_ROOT],
    binaries=_collect_linux_enchant_binaries(),
    datas=_EXTRA_DATAS,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "PySide6.QtWebEngineCore",
        "PySide6.QtWebEngineWidgets",
        "PySide6.QtWebEngineQuick",
        "PySide6.QtWebChannel",
        "PySide6.QtQml",
        "PySide6.QtQmlModels",
        "PySide6.QtQmlWorkerScript",
        "PySide6.QtQuick",
        "PySide6.QtQuickWidgets",
        "PySide6.QtQuickControls2",
        "PySide6.QtQuickTemplates2",
        "PySide6.Qt3DCore",
        "PySide6.Qt3DRender",
        "PySide6.Qt3DInput",
        "PySide6.Qt3DLogic",
        "PySide6.Qt3DExtras",
        "PySide6.Qt3DAnimation",
        "PySide6.QtMultimedia",
        "PySide6.QtMultimediaWidgets",
        "PySide6.QtPdf",
        "PySide6.QtPdfWidgets",
        "PySide6.QtDesigner",
        "PySide6.QtHelp",
        "PySide6.QtPositioning",
        "PySide6.QtSensors",
        "PySide6.QtSerialPort",
        "PySide6.QtSpatialAudio",
        "PySide6.QtSql",
        "PySide6.QtTest",
        "tkinter",
        "pytest",
        "mypy",
    ],
    noarchive=False,
    module_collection_mode={"enchant": "py"},
    optimize=0,
)

a.binaries = [b for b in a.binaries if _keep_binary(b)]
a.datas = [d for d in a.datas if _keep_data(d)]

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="i18n-reviewer",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="i18n-reviewer",
)

