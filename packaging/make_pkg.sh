#!/usr/bin/env bash
# Build AudioTools-macos-*.pkg from an existing PyInstaller onedir output.
# Primary end-user installer — Installer.app copies to /Applications (no DMG mount).
# This script does NOT run PyInstaller — rebuild first if ui/ sources changed.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

chmod +x packaging/make_app.sh
./packaging/make_app.sh
# Sign the .app before wrapping it so the installer payload is Gatekeeper-ready.
python3 packaging/macos_signing.py sign-app dist/AudioTools.app

APP_VERSION="${AUDIO_TOOLS_VERSION:-0.1.3}"
BIN_ARCHS="$(lipo -archs dist/AudioTools/AudioTools 2>/dev/null || true)"
if grep -qw arm64 <<<"$BIN_ARCHS"; then
  PKG_NAME="AudioTools-${APP_VERSION}-macos-arm64-silicon.pkg"
elif grep -Ewq 'x86_64' <<<"$BIN_ARCHS"; then
  PKG_NAME="AudioTools-${APP_VERSION}-macos-x64-intel.pkg"
else
  echo "Unsupported binary architecture: ${BIN_ARCHS:-unknown}" >&2
  exit 1
fi

OUTPUT_DIR="${AUDIO_TOOLS_OUTPUT_DIR:-$HOME/Downloads}"
mkdir -p "$OUTPUT_DIR"
PKG_PATH="$OUTPUT_DIR/${AUDIO_TOOLS_PKG_NAME:-$PKG_NAME}"

PKG_ROOT="dist/pkg_root"
rm -rf "$PKG_ROOT"
mkdir -p "$PKG_ROOT"
ditto --norsrc --noextattr --noqtn dist/AudioTools.app "$PKG_ROOT/AudioTools.app"
xattr -cr "$PKG_ROOT/AudioTools.app" 2>/dev/null || true

SCRIPTS_DIR="packaging/pkg_scripts"
chmod +x "$SCRIPTS_DIR/postinstall"

rm -f "$PKG_PATH"
# BundleIsRelocatable must be false. Otherwise Installer "succeeds" by
# upgrading a leftover AudioTools.app under dist/ and never writes /Applications.
pkgbuild \
  --root "$PKG_ROOT" \
  --install-location /Applications \
  --identifier local.audiotools.desktop \
  --version "$APP_VERSION" \
  --component-plist packaging/pkg_component.plist \
  --scripts "$SCRIPTS_DIR" \
  "$PKG_PATH"

python3 packaging/macos_signing.py sign-pkg --app dist/AudioTools.app --pkg "$PKG_PATH"
xattr -cr "$PKG_PATH" 2>/dev/null || true

echo "Created $PKG_PATH"
