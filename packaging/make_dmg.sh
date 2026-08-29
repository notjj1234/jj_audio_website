#!/usr/bin/env bash
# Build AudioTools-macos-*.dmg from an existing PyInstaller onedir output.
# Maintainer fallback — prefer make_pkg.sh for end-user installers.
# This script does NOT run PyInstaller — rebuild first if ui/ sources changed.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

chmod +x packaging/make_app.sh
./packaging/make_app.sh
python3 packaging/macos_signing.py sign-app dist/AudioTools.app

APP_VERSION="${AUDIO_TOOLS_VERSION:-0.1.2}"
BIN_ARCHS="$(lipo -archs dist/AudioTools/AudioTools 2>/dev/null || true)"
if grep -qw arm64 <<<"$BIN_ARCHS"; then
  DMG_NAME="AudioTools-${APP_VERSION}-macos-arm64-silicon.dmg"
elif grep -Ewq 'x86_64' <<<"$BIN_ARCHS"; then
  DMG_NAME="AudioTools-${APP_VERSION}-macos-x64-intel.dmg"
else
  echo "Unsupported binary architecture: ${BIN_ARCHS:-unknown}" >&2
  exit 1
fi

OUTPUT_DIR="${AUDIO_TOOLS_OUTPUT_DIR:-$HOME/Downloads}"
mkdir -p "$OUTPUT_DIR"
DMG_PATH="$OUTPUT_DIR/${AUDIO_TOOLS_DMG_NAME:-$DMG_NAME}"

APP_DIR="dist/AudioTools.app"
STAGE="dist/dmg_stage"
rm -rf "$STAGE"
mkdir -p "$STAGE"
cp -R "$APP_DIR" "$STAGE/"
ln -sf /Applications "$STAGE/Applications"

INSTALL_CMD="packaging/Install AudioTools.command"
cp "$INSTALL_CMD" "$STAGE/Install AudioTools.command"
chmod +x "$STAGE/Install AudioTools.command"

# Versioned volume name so leftover mounts (if any) are identifiable — prefer
# Install AudioTools.command which ejects after copy.
VOLNAME="AudioTools-${APP_VERSION}"

rm -f "$DMG_PATH"
hdiutil create -volname "$VOLNAME" -srcfolder "$STAGE" -ov -format UDZO "$DMG_PATH"

echo "Created $DMG_PATH"
