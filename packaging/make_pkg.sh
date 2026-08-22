#!/usr/bin/env bash
# Build AudioTools-macos-*.pkg from an existing PyInstaller onedir output.
# Primary end-user installer — Installer.app copies to /Applications (no DMG mount).
# This script does NOT run PyInstaller — rebuild first if ui/ sources changed.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

chmod +x packaging/make_app.sh
./packaging/make_app.sh

APP_VERSION="${AUDIO_TOOLS_VERSION:-1.0.0}"
ARCH="$(uname -m)"

if [[ "$ARCH" == "arm64" ]]; then
  PKG_NAME="AudioTools-${APP_VERSION}-macos-arm64.pkg"
elif [[ "$ARCH" == "x86_64" ]]; then
  PKG_NAME="AudioTools-${APP_VERSION}-macos-x64.pkg"
else
  echo "Unsupported architecture: $ARCH" >&2
  exit 1
fi

OUTPUT_DIR="${AUDIO_TOOLS_OUTPUT_DIR:-$HOME/Downloads}"
mkdir -p "$OUTPUT_DIR"
PKG_PATH="$OUTPUT_DIR/${AUDIO_TOOLS_PKG_NAME:-$PKG_NAME}"

PKG_ROOT="dist/pkg_root"
rm -rf "$PKG_ROOT"
mkdir -p "$PKG_ROOT"
cp -R dist/AudioTools.app "$PKG_ROOT/"

SCRIPTS_DIR="packaging/pkg_scripts"
chmod +x "$SCRIPTS_DIR/postinstall"

rm -f "$PKG_PATH"
pkgbuild \
  --root "$PKG_ROOT" \
  --install-location /Applications \
  --identifier local.audiotools.desktop \
  --version "$APP_VERSION" \
  --scripts "$SCRIPTS_DIR" \
  "$PKG_PATH"

echo "Created $PKG_PATH"
