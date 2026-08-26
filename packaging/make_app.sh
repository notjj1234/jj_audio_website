#!/usr/bin/env bash
# Build dist/AudioTools.app from an existing PyInstaller onedir output.
# Shared by make_dmg.sh and make_pkg.sh — does NOT run PyInstaller.
# macOS .app bundles require onedir contents in Contents/Frameworks (not MacOS).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ ! -x dist/AudioTools/AudioTools ]]; then
  echo "Missing dist/AudioTools/AudioTools — run pyinstaller packaging/audio_tools.spec first." >&2
  exit 1
fi

if [[ ! -d dist/AudioTools/_internal ]]; then
  echo "Missing dist/AudioTools/_internal — expected PyInstaller onedir layout." >&2
  exit 1
fi

if [[ ! -f dist/AudioTools/_internal/ui/icon.png ]]; then
  echo "Stale PyInstaller output: dist/AudioTools/_internal/ui/icon.png is missing." >&2
  echo "Re-run: pyinstaller packaging/audio_tools.spec --noconfirm --clean" >&2
  exit 1
fi

if [[ ! -f dist/AudioTools/_internal/ui/stem_mixer_component/frontend/build/index.html ]]; then
  echo "Mixer frontend missing from dist — run: make mixer-build && pyinstaller packaging/audio_tools.spec --noconfirm --clean" >&2
  exit 1
fi

# Name from the freeze, not the host, so an Intel onedir can be wrapped on Apple Silicon.
BIN_ARCHS="$(lipo -archs dist/AudioTools/AudioTools 2>/dev/null || true)"
if grep -qw arm64 <<<"$BIN_ARCHS"; then
  ARCH="arm64"
elif grep -Ewq 'x86_64' <<<"$BIN_ARCHS"; then
  ARCH="x86_64"
else
  echo "Unsupported PyInstaller binary architecture: ${BIN_ARCHS:-unknown}" >&2
  exit 1
fi

APP_VERSION="${AUDIO_TOOLS_VERSION:-0.1.1}"
APP_DIR="dist/AudioTools.app"
rm -rf "$APP_DIR"
mkdir -p "$APP_DIR/Contents/MacOS" "$APP_DIR/Contents/Frameworks" "$APP_DIR/Contents/Resources"

# Refresh Streamlit sources so a stale PyInstaller freeze still ships current UI.
if [[ -d dist/AudioTools/_internal/ui ]]; then
  if [[ -f ui/pages/isolate.py ]]; then
    ditto --norsrc --noextattr --noqtn ui/pages/isolate.py dist/AudioTools/_internal/ui/pages/isolate.py
  fi
  if [[ -f ui/media.py ]]; then
    ditto --norsrc --noextattr --noqtn ui/media.py dist/AudioTools/_internal/ui/media.py
  fi
fi

# ditto --noqtn/--noextattr drops downloaded-file quarantine so it is not baked in.
ditto --norsrc --noextattr --noqtn dist/AudioTools/AudioTools "$APP_DIR/Contents/MacOS/AudioTools"
chmod +x "$APP_DIR/Contents/MacOS/AudioTools"
ditto --norsrc --noextattr --noqtn dist/AudioTools/_internal "$APP_DIR/Contents/Frameworks"

if [[ -f packaging/icon.icns ]]; then
  ditto --norsrc --noextattr --noqtn packaging/icon.icns "$APP_DIR/Contents/Resources/AppIcon.icns"
fi
xattr -cr "$APP_DIR" 2>/dev/null || true

APP_VERSION="$APP_VERSION" python3 - <<'PY'
import os
from pathlib import Path

version = os.environ["APP_VERSION"]
plist = Path("dist/AudioTools.app/Contents/Info.plist")
plist.write_text(
    f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleExecutable</key>
  <string>AudioTools</string>
  <key>CFBundleIdentifier</key>
  <string>local.audiotools.desktop</string>
  <key>CFBundleName</key>
  <string>AudioTools</string>
  <key>CFBundlePackageType</key>
  <string>APPL</string>
  <key>CFBundleShortVersionString</key>
  <string>{version}</string>
  <key>CFBundleIconFile</key>
  <string>AppIcon</string>
  <key>CFBundleVersion</key>
  <string>{version}</string>
  <key>LSMinimumSystemVersion</key>
  <string>12.0</string>
  <key>NSHighResolutionCapable</key>
  <true/>
</dict>
</plist>
""",
    encoding="utf-8",
)
PY

echo "Created $ROOT/$APP_DIR (version $APP_VERSION, arch $ARCH)"
