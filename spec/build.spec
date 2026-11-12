# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller specification for i18n Reviewer (Windows x64 --onedir --windowed)."""

from __future__ import annotations

import os
import enchant

PROJECT_ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))
_ENCHANT_HUNSPELL_DIR = os.path.join(
    os.path.dirname(enchant.__file__), "data", "mingw64", "share", "enchant", "hunspell"
)

_ALLOWED_ENCHANT_BINARIES = {
    "enchant/data/mingw64/bin/libenchant-2.dll",
    "enchant/data/mingw64/bin/libgcc_s_seh-1.dll",
    "enchant/data/mingw64/bin/libglib-2.0-0.dll",
    "enchant/data/mingw64/bin/libgmodule-2.0-0.dll",
    "enchant/data/mingw64/bin/libhunspell-1.7-0.dll",
    "enchant/data/mingw64/bin/libiconv-2.dll",
    "enchant/data/mingw64/bin/libintl-8.dll",
    "enchant/data/mingw64/bin/libpcre2-8-0.dll",
    "enchant/data/mingw64/bin/libstdc++-6.dll",
    "enchant/data/mingw64/bin/libwinpthread-1.dll",
    "enchant/data/mingw64/lib/enchant-2/enchant_hunspell.dll",
}

_ALLOWED_ENCHANT_DATAS = {
    "enchant/data/mingw64/share/enchant/enchant.ordering",
    "enchant/data/mingw64/share/enchant/hunspell/en_us.aff",
    "enchant/data/mingw64/share/enchant/hunspell/en_us.dic",
}

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
_EXCLUDED_QT_BIN_PREFIXES = tuple(f"qt6{m}" for m in _EXCLUDED_QT_MODULES)
_EXCLUDED_QT_DATA_PREFIXES = tuple(f"qt{m}" for m in _EXCLUDED_QT_MODULES)


def _norm_dest(entry: tuple[str, ...]) -> str:
    return entry[0].replace("\\", "/").lower()


def _keep_binary(entry: tuple[str, ...]) -> bool:
    dest = _norm_dest(entry)
    fname = dest.rsplit("/", 1)[-1]
    if fname.startswith(_EXCLUDED_QT_BIN_PREFIXES):
        return False
    if dest.startswith("enchant/data/"):
        return dest in _ALLOWED_ENCHANT_BINARIES
    return True


def _keep_data(entry: tuple[str, ...]) -> bool:
    dest = _norm_dest(entry)
    fname = dest.rsplit("/", 1)[-1]
    if dest.startswith("enchant/data/"):
        return dest in _ALLOWED_ENCHANT_DATAS
    if fname.startswith(_EXCLUDED_QT_DATA_PREFIXES):
        return False
    return True


_EXTRA_DATAS = [
    (os.path.join(PROJECT_ROOT, "resources", "hunspell"), os.path.join("resources", "hunspell")),
    (os.path.join(PROJECT_ROOT, "licenses"), "licenses"),
]
for _en_name in ("en_US.aff", "en_US.dic"):
    _en_src = os.path.join(_ENCHANT_HUNSPELL_DIR, _en_name)
    if os.path.exists(_en_src):
        _EXTRA_DATAS.append((_en_src, os.path.join("resources", "hunspell")))


a = Analysis(
    [os.path.join(PROJECT_ROOT, "app", "main.py")],
    pathex=[PROJECT_ROOT],
    binaries=[],
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
