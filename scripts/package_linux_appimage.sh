#!/usr/bin/env bash
set -euo pipefail

VERSION="0.1.0"
SKIP_BUILD=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --version)
      VERSION="${2#v}"
      shift 2
      ;;
    --skip-build)
      SKIP_BUILD=1
      shift
      ;;
    *)
      echo "Unknown argument: $1" >&2
      exit 2
      ;;
  esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

PYINSTALLER="$REPO_ROOT/.venv/bin/pyinstaller"
DIST_BUNDLE="$REPO_ROOT/dist/i18n-reviewer"
APPDIR="$REPO_ROOT/build/AppDir"
OUT_APPIMAGE="$REPO_ROOT/dist/i18n-reviewer-${VERSION}-x86_64.AppImage"
TOOLS_DIR="$REPO_ROOT/build/tools"
APPIMAGETOOL="${APPIMAGETOOL:-$TOOLS_DIR/appimagetool-x86_64.AppImage}"

if [[ "$SKIP_BUILD" -eq 0 ]]; then
  if [[ ! -x "$PYINSTALLER" ]]; then
    echo "PyInstaller not found at $PYINSTALLER. Install requirements-dev.txt first." >&2
    exit 1
  fi
  echo "Building i18n-reviewer Linux bundle via PyInstaller..."
  "$PYINSTALLER" --clean -y "$REPO_ROOT/spec/build_linux.spec"
fi

if [[ ! -x "$DIST_BUNDLE/i18n-reviewer" ]]; then
  echo "Frozen binary not found at $DIST_BUNDLE/i18n-reviewer" >&2
  exit 1
fi

echo "Running --self-test on PyInstaller bundle..."
QT_QPA_PLATFORM=offscreen "$DIST_BUNDLE/i18n-reviewer" --self-test

rm -rf "$APPDIR"
mkdir -p \
  "$APPDIR/usr/bin" \
  "$APPDIR/usr/lib/i18n-reviewer" \
  "$APPDIR/usr/share/applications" \
  "$APPDIR/usr/share/icons/hicolor/scalable/apps"

cp -a "$DIST_BUNDLE/." "$APPDIR/usr/lib/i18n-reviewer/"
ln -sf "../lib/i18n-reviewer/i18n-reviewer" "$APPDIR/usr/bin/i18n-reviewer"

cp "$REPO_ROOT/packaging/linux/i18n-reviewer.desktop" "$APPDIR/i18n-reviewer.desktop"
cp "$REPO_ROOT/packaging/linux/i18n-reviewer.desktop" "$APPDIR/usr/share/applications/i18n-reviewer.desktop"
cp "$REPO_ROOT/resources/icons/i18n-reviewer.svg" "$APPDIR/i18n-reviewer.svg"
cp "$REPO_ROOT/resources/icons/i18n-reviewer.svg" "$APPDIR/usr/share/icons/hicolor/scalable/apps/i18n-reviewer.svg"
ln -sf "i18n-reviewer.svg" "$APPDIR/.DirIcon"

cp "$REPO_ROOT/packaging/linux/AppRun" "$APPDIR/AppRun"
sed -i 's/\r$//' "$APPDIR/AppRun"
chmod +x "$APPDIR/AppRun" "$APPDIR/usr/lib/i18n-reviewer/i18n-reviewer"

if [[ ! -x "$APPIMAGETOOL" ]]; then
  mkdir -p "$TOOLS_DIR"
  echo "Downloading appimagetool-x86_64.AppImage..."
  curl -fsSL -L -o "$APPIMAGETOOL" \
    "https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage"
  chmod +x "$APPIMAGETOOL"
fi

rm -f "$OUT_APPIMAGE"
echo "Packaging AppImage at $OUT_APPIMAGE..."
ARCH=x86_64 APPIMAGE_EXTRACT_AND_RUN=1 "$APPIMAGETOOL" --no-appstream "$APPDIR" "$OUT_APPIMAGE"
chmod +x "$OUT_APPIMAGE"

echo "Running --self-test on packaged AppImage (normal path)..."
QT_QPA_PLATFORM=offscreen APPIMAGE_EXTRACT_AND_RUN=1 "$OUT_APPIMAGE" --self-test

NON_ASCII_DIR="$(mktemp -d "/tmp/i18n_ação_appimage_XXXXXX")"
trap 'rm -rf "$NON_ASCII_DIR"' EXIT
cp "$OUT_APPIMAGE" "$NON_ASCII_DIR/i18n-reviewer.AppImage"
chmod +x "$NON_ASCII_DIR/i18n-reviewer.AppImage"
echo "Running --self-test on packaged AppImage (non-ASCII path: $NON_ASCII_DIR)..."
QT_QPA_PLATFORM=offscreen APPIMAGE_EXTRACT_AND_RUN=1 "$NON_ASCII_DIR/i18n-reviewer.AppImage" --self-test

echo "AppImage ready: $OUT_APPIMAGE"

