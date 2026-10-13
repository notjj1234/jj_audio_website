#!/usr/bin/env bash
# Regenerate favicon / desktop icons from packaging/icon-source.png (1024×1024 square).
# Applies a macOS-style squircle alpha mask → packaging/icon.png, then all derivatives.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

SOURCE="packaging/icon-source.png"
OUT="packaging/icon.png"

# First-time migrate: if only the old square master exists, keep it as source.
if [[ ! -f "$SOURCE" && -f "$OUT" ]]; then
  cp "$OUT" "$SOURCE"
fi
if [[ ! -f "$SOURCE" ]]; then
  echo "Missing $SOURCE — add a 1024×1024 square PNG master first." >&2
  exit 1
fi

python3 - <<'PY'
"""Squircle-mask master art, then inset for macOS Dock optical size."""
from __future__ import annotations

from PIL import Image

SOURCE = "packaging/icon-source.png"
OUT = "packaging/icon.png"
# n≈5 matches the continuous-corner “squircle” look better than circular radii.
SUPERELLIPSE_N = 5.0
# Render mask at 2× then downsample for soft edges.
SCALE = 2
# Apple-style margin: glyph fills this fraction of the canvas (rest transparent).
ICON_CONTENT_SCALE = 0.82


def squircle_mask(size: int, n: float = SUPERELLIPSE_N) -> Image.Image:
    big = size * SCALE
    cover = bytearray(big * big)
    cx = cy = (big - 1) / 2.0
    rx = ry = big / 2.0
    for y in range(big):
        ny = abs((y - cy) / ry)
        row = y * big
        for x in range(big):
            nx = abs((x - cx) / rx)
            if nx ** n + ny ** n <= 1.0:
                cover[row + x] = 255
    mask_big = Image.frombytes("L", (big, big), bytes(cover))
    return mask_big.resize((size, size), Image.Resampling.LANCZOS)


def clear_transparent_rgb(im: Image.Image) -> None:
    # iconutil is picky about associated alpha.
    px = im.load()
    w, h = im.size
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if a == 0:
                px[x, y] = (0, 0, 0, 0)


src = Image.open(SOURCE).convert("RGBA")
w, h = src.size
if w != h:
    raise SystemExit(f"Icon source must be square, got {w}×{h}")
mask = squircle_mask(w)
masked = Image.new("RGBA", src.size, (0, 0, 0, 0))
masked.paste(src, (0, 0))
masked.putalpha(mask)
clear_transparent_rgb(masked)

inner = max(1, int(round(w * ICON_CONTENT_SCALE)))
scaled = masked.resize((inner, inner), Image.Resampling.LANCZOS)
out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
offset = (w - inner) // 2
out.paste(scaled, (offset, offset), scaled)
clear_transparent_rgb(out)
out.save(OUT, format="PNG")
print(
    f"Wrote {OUT} ({w}×{h}, squircle + content scale {ICON_CONTENT_SCALE})"
)
PY

SRC="$OUT"
mkdir -p web/public ui
cp "$SRC" ui/icon.png

# Build iconset + web sizes with PIL (sips + alpha often yields "Invalid Iconset").
python3 - <<'PY'
from pathlib import Path
from PIL import Image

src = Image.open("packaging/icon.png").convert("RGBA")
iconset = Path("packaging/icon.iconset")
if iconset.exists():
    for p in iconset.iterdir():
        p.unlink()
else:
    iconset.mkdir(parents=True)

def save_png(path: Path, size: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    src.resize((size, size), Image.Resampling.LANCZOS).save(path, format="PNG")

# macOS .iconset names
for name, size in (
    ("icon_16x16.png", 16),
    ("icon_16x16@2x.png", 32),
    ("icon_32x32.png", 32),
    ("icon_32x32@2x.png", 64),
    ("icon_128x128.png", 128),
    ("icon_128x128@2x.png", 256),
    ("icon_256x256.png", 256),
    ("icon_256x256@2x.png", 512),
    ("icon_512x512.png", 512),
    ("icon_512x512@2x.png", 1024),
):
    save_png(iconset / name, size)

save_png(Path("web/public/favicon-32x32.png"), 32)
save_png(Path("web/public/apple-touch-icon.png"), 180)
save_png(Path("web/public/icon-512.png"), 512)

sizes = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
src.save("packaging/icon.ico", sizes=sizes)
src.save("web/public/favicon.ico", sizes=sizes)
print("Wrote iconset + favicons")
PY

iconutil -c icns packaging/icon.iconset -o packaging/icon.icns
rm -rf packaging/icon.iconset

echo "Icons updated from $SOURCE → $SRC (squircle mask applied)"
