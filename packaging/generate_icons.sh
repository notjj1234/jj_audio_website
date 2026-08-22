#!/usr/bin/env bash
# Regenerate favicon / desktop icons from packaging/icon.png (1024×1024 master).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

SRC="packaging/icon.png"
if [[ ! -f "$SRC" ]]; then
  echo "Missing $SRC — add a 1024×1024 PNG master first." >&2
  exit 1
fi

mkdir -p web/public ui
cp "$SRC" ui/icon.png

sips -z 32 32 "$SRC" --out web/public/favicon-32x32.png
sips -z 180 180 "$SRC" --out web/public/apple-touch-icon.png
sips -z 512 512 "$SRC" --out web/public/icon-512.png

ICONSET="packaging/icon.iconset"
rm -rf "$ICONSET"
mkdir -p "$ICONSET"
sips -z 16 16 "$SRC" --out "$ICONSET/icon_16x16.png"
sips -z 32 32 "$SRC" --out "$ICONSET/icon_16x16@2x.png"
sips -z 32 32 "$SRC" --out "$ICONSET/icon_32x32.png"
sips -z 64 64 "$SRC" --out "$ICONSET/icon_32x32@2x.png"
sips -z 128 128 "$SRC" --out "$ICONSET/icon_128x128.png"
sips -z 256 256 "$SRC" --out "$ICONSET/icon_128x128@2x.png"
sips -z 256 256 "$SRC" --out "$ICONSET/icon_256x256.png"
sips -z 512 512 "$SRC" --out "$ICONSET/icon_256x256@2x.png"
sips -z 512 512 "$SRC" --out "$ICONSET/icon_512x512.png"
sips -z 1024 1024 "$SRC" --out "$ICONSET/icon_512x512@2x.png"
iconutil -c icns "$ICONSET" -o packaging/icon.icns
rm -rf "$ICONSET"

python3 - <<'PY'
from PIL import Image

img = Image.open("packaging/icon.png").convert("RGBA")
sizes = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
img.save("packaging/icon.ico", sizes=sizes)
img.save("web/public/favicon.ico", sizes=sizes)
PY

echo "Icons updated from $SRC"
