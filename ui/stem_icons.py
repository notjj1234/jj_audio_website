"""Line-art stem icons for Lite/Pro New tiles.

Embedded as Streamlit button-label Markdown images (data URIs) so the desktop
app stays offline — no CDN at runtime.

Icon sources:
- Lucide Icons (ISC): mic, guitar, drum, piano, audio-waveform, music
  https://lucide.dev — https://github.com/lucide-icons/lucide
- Bass: original Lucide-matching stroke companion (Lucide has no bass glyph).
Not Moises artwork.
"""

from __future__ import annotations

import base64

# Coral on unselected tiles; white baked into selected labels (Streamlit primary
# button DOM does not reliably accept a CSS filter on Markdown <img>).
_PRIMARY = "#ff4b4b"
_ON_PRIMARY = "#ffffff"
_ATTRS = (
    f'xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
    f'stroke="{_PRIMARY}" stroke-width="2.25" stroke-linecap="round" '
    f'stroke-linejoin="round"'
)


def _svg(inner: str) -> str:
    return f"<svg {_ATTRS}>{inner}</svg>"


# Lucide: mic (ISC)
_MIC = _svg(
    '<path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z"/>'
    '<path d="M19 10v2a7 7 0 0 1-14 0v-2"/>'
    '<line x1="12" x2="12" y1="19" y2="22"/>'
)

# Lucide: guitar (ISC)
_GUITAR = _svg(
    '<path d="m11.9 12.1 4.514-4.514"/>'
    '<path d="M20.1 2.3a1 1 0 0 0-1.4 0l-1.114 1.114A2 2 0 0 0 17 4.828v1.344a2 2 0 0 1-.586 1.414A2 2 0 0 1 17.828 7h1.344a2 2 0 0 0 1.414-.586L21.7 5.3a1 1 0 0 0 0-1.4z"/>'
    '<path d="m6 16 2 2"/>'
    '<path d="M8.2 9.9C8.7 8.8 9.8 8 11 8c2.8 0 5 2.2 5 5 0 1.2-.8 2.3-1.9 2.8l-.9.4A2 2 0 0 0 12 18a4 4 0 0 1-4 4c-3.3 0-6-2.7-6-6a4 4 0 0 1 4-4 2 2 0 0 0 1.8-1.2z"/>'
    f'<circle cx="11.5" cy="12.5" r=".5" fill="{_PRIMARY}"/>'
)

# Original Lucide-style bass (longer neck, smaller body, 4 pegs) — no Lucide bass.
_BASS = _svg(
    '<path d="M7.2 15.8c-.4-1.1.2-2.4 1.2-3 1.5-.9 3.2-.4 4.1.9.5.7.5 1.6.1 2.4l-.6 1.1A2 2 0 0 0 12 19a3.5 3.5 0 0 1-3.5 3.5C5.6 22.5 3 20 3 16.8c0-2 1.4-3.6 3.2-3.9.7-.1 1.3-.5 1.6-1.1z"/>'
    f'<circle cx="8.6" cy="16.2" r=".55" fill="{_PRIMARY}"/>'
    '<path d="m10.4 13.6 8.2-8.6"/>'
    '<path d="M17.8 3.2h3.6v3.2"/>'
    f'<circle cx="18.4" cy="2.6" r=".55" fill="{_PRIMARY}" stroke="none"/>'
    f'<circle cx="20.2" cy="2.6" r=".55" fill="{_PRIMARY}" stroke="none"/>'
    f'<circle cx="21.8" cy="4.2" r=".55" fill="{_PRIMARY}" stroke="none"/>'
    f'<circle cx="21.8" cy="6" r=".55" fill="{_PRIMARY}" stroke="none"/>'
)

# Lucide: drum (ISC)
_DRUMS = _svg(
    '<path d="m2 2 8 8"/>'
    '<path d="m22 2-8 8"/>'
    '<ellipse cx="12" cy="9" rx="10" ry="5"/>'
    '<path d="M7 13.4v7.9"/>'
    '<path d="M12 14v8"/>'
    '<path d="M17 13.4v7.9"/>'
    '<path d="M2 9v8a10 5 0 0 0 20 0V9"/>'
)

# Lucide: piano (ISC)
_PIANO = _svg(
    '<path d="M18.5 8c-1.4 0-2.6-.8-3.2-2A6.87 6.87 0 0 0 2 9v11a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-8.5C22 9.6 20.4 8 18.5 8"/>'
    '<path d="M2 14h20"/>'
    '<path d="M6 14v4"/>'
    '<path d="M10 14v4"/>'
    '<path d="M14 14v4"/>'
    '<path d="M18 14v4"/>'
)

# Lucide: audio-waveform (ISC) — residual / other
_OTHER = _svg(
    '<path d="M2 13a2 2 0 0 0 2-2V7a2 2 0 0 1 4 0v13a2 2 0 0 0 4 0V4a2 2 0 0 1 4 0v13a2 2 0 0 0 4 0v-4a2 2 0 0 1 2-2"/>'
)

# Lucide: music (ISC) — full-mix / band preset
_BAND = _svg(
    '<path d="M9 18V5l12-2v13"/>'
    '<circle cx="6" cy="18" r="3"/>'
    '<circle cx="18" cy="16" r="3"/>'
)

STEM_ICON_SVG: dict[str, str] = {
    "vocals": _MIC,
    "guitar": _GUITAR,
    "bass": _BASS,
    "drums": _DRUMS,
    "piano": _PIANO,
    "other": _OTHER,
}

OUTCOME_ICON_SVG: dict[str, str] = {
    "band": _BAND,
    "karaoke": _MIC,
    "guitar": _GUITAR,
    "vocals": _MIC,
}


def icon_data_uri(svg: str) -> str:
    payload = base64.standard_b64encode(svg.encode("utf-8")).decode("ascii")
    return f"data:image/svg+xml;base64,{payload}"


def icon_markdown(svg: str, *, alt: str) -> str:
    """Streamlit button labels accept GFM images; they render at text height."""
    return f"![{alt}]({icon_data_uri(svg)})"


def _svg_for_selection(svg: str, *, selected: bool) -> str:
    if selected:
        return svg.replace(_PRIMARY, _ON_PRIMARY)
    return svg


def stem_icon_markdown(stem_id: str, *, selected: bool = False) -> str:
    svg = STEM_ICON_SVG.get(stem_id)
    if not svg:
        return ""
    return icon_markdown(_svg_for_selection(svg, selected=selected), alt=stem_id)


def outcome_icon_markdown(card_id: str, *, selected: bool = False) -> str:
    svg = OUTCOME_ICON_SVG.get(card_id)
    if not svg:
        return ""
    return icon_markdown(_svg_for_selection(svg, selected=selected), alt=card_id)
