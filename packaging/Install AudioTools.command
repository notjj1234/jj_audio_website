#!/usr/bin/env bash
# Double-click from the mounted DMG: copy to /Applications, then eject this volume
# so Finder does not keep stacking "AudioTools" disks in the sidebar.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
APP_SRC="$HERE/AudioTools.app"

if [[ ! -d "$APP_SRC" ]]; then
  osascript -e 'display alert "AudioTools.app was not found on this disk." as critical' >/dev/null 2>&1 || true
  exit 1
fi

rm -rf /Applications/AudioTools.app
cp -R "$APP_SRC" /Applications/
xattr -dr com.apple.quarantine /Applications/AudioTools.app 2>/dev/null || true

# Eject this DMG volume (only when running from /Volumes/…).
if [[ "$HERE" == /Volumes/* ]]; then
  # Prefer quiet detach; fall back if Finder still has the window open.
  hdiutil detach "$HERE" -quiet 2>/dev/null \
    || hdiutil detach "$HERE" -force -quiet 2>/dev/null \
    || diskutil unmount force "$HERE" >/dev/null 2>&1 \
    || true
fi

osascript -e 'display notification "Installed to Applications. The installer disk was ejected." with title "AudioTools"' >/dev/null 2>&1 || true
open /Applications/AudioTools.app
