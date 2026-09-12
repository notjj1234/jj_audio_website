"""Offline Satoshi @font-face CSS for the Streamlit shell (no CDN)."""

from __future__ import annotations

import base64
from functools import lru_cache
from pathlib import Path

_FONT_DIR = Path(__file__).resolve().parent / "fonts" / "satoshi"
_WEIGHTS: tuple[tuple[int, str], ...] = (
    (300, "Light"),
    (400, "Regular"),
    (500, "Medium"),
    (700, "Bold"),
    (900, "Black"),
)


@lru_cache(maxsize=1)
def satoshi_font_face_css() -> str:
    """Return @font-face rules with embedded woff2 data URIs."""
    parts: list[str] = []
    for weight, name in _WEIGHTS:
        path = _FONT_DIR / f"Satoshi-{name}.woff2"
        if not path.is_file():
            continue
        b64 = base64.b64encode(path.read_bytes()).decode("ascii")
        parts.append(
            f"""@font-face {{
  font-family: "Satoshi";
  src: url("data:font/woff2;base64,{b64}") format("woff2");
  font-weight: {weight};
  font-style: normal;
  font-display: swap;
}}"""
        )
    return "\n".join(parts)
