"""Home-only tokens for AUDIO_TOOLS_UI_V2.

Do not import this from the mixer. Do not copy these values into theme presets.
"""

from __future__ import annotations

import os

# Page background. Measured #101213.
HOME_BG = "#101213"
HOME_CARD = "#17191C"
HOME_WASH = "rgba(202, 224, 250, 0.08)"
HOME_WASH_HOVER = "rgba(202, 224, 250, 0.14)"
HOME_TEXT = "rgba(239, 246, 255, 0.97)"
HOME_TEXT_SECONDARY = "rgba(225, 236, 249, 0.75)"
# 12px meta. Measured composite is 4.38:1 on #101213. Waiver: kept for the
# measured alpha on meta text only. Group labels do not use this color.
HOME_TEXT_META = "rgba(216, 233, 254, 0.49)"
# Measured muted alpha composites to about #57606A at 2.94:1. Each channel was
# lifted by the same amount until contrast on #101213 cleared 4.5:1.
# #757E88 is that first passing step (about 4.56:1). The measured alpha is not shipped.
HOME_TEXT_MUTED = "#757E88"
HOME_CHIP = "#ACB5BF"
HOME_SELECTED = "#E9EEF5"
HOME_ICON_ACCENT = "#75EBF5"
HOME_ICON = "#E9EEF5"
HOME_LINE = "#E9EEF5"
HOME_WORDMARK = "#EDEEF0"

HOME_TOKENS: dict[str, str] = {
    "bg": HOME_BG,
    "card": HOME_CARD,
    "wash": HOME_WASH,
    "wash_hover": HOME_WASH_HOVER,
    "text": HOME_TEXT,
    "text_secondary": HOME_TEXT_SECONDARY,
    "text_meta": HOME_TEXT_META,
    "text_muted": HOME_TEXT_MUTED,
    "chip": HOME_CHIP,
    "selected": HOME_SELECTED,
    "icon_accent": HOME_ICON_ACCENT,
    "icon": HOME_ICON,
    "line": HOME_LINE,
    "wordmark": HOME_WORDMARK,
}


def ui_v2_enabled() -> bool:
    """The clean Home is the default. Set AUDIO_TOOLS_UI_V2=0 to keep the old page."""
    raw = os.environ.get("AUDIO_TOOLS_UI_V2", "1").strip().lower()
    return raw not in {"0", "false", "no", "off"}


def _channel(value: float) -> float:
    value = value / 255.0
    if value <= 0.04045:
        return value / 12.92
    return ((value + 0.055) / 1.055) ** 2.4


def _luminance(hex_color: str) -> float:
    raw = hex_color.removeprefix("#")
    red = int(raw[0:2], 16)
    green = int(raw[2:4], 16)
    blue = int(raw[4:6], 16)
    return 0.2126 * _channel(red) + 0.7152 * _channel(green) + 0.0722 * _channel(blue)


def contrast_ratio(foreground: str, background: str) -> float:
    """WCAG contrast for two opaque hex colors."""
    lighter = max(_luminance(foreground), _luminance(background))
    darker = min(_luminance(foreground), _luminance(background))
    return (lighter + 0.05) / (darker + 0.05)


def _mask(svg: str) -> str:
    encoded = (
        svg.replace("\n", "")
        .replace('"', "'")
        .replace("#", "%23")
        .replace("<", "%3C")
        .replace(">", "%3E")
    )
    return f"url(\"data:image/svg+xml,{encoded}\")"


# Original filled icons. viewBox 0 0 16 16. Not copied from another product.
_ICON_HOME = (
    "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'>"
    "<path fill='%23000' d='M8 1.4 1.2 7.2V14.6h4.4V9.6h4.8v5H14.8V7.2z'/></svg>"
)
_ICON_WAVE = (
    "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'>"
    "<path fill='%23000' d='M1 8h2.2V6H1zm3.4-4h2.2V12H4.4zm3.4 2.2h2.2v5.6H7.8zM11.2 2.4H13.4V13.6h-2.2z'/></svg>"
)
_ICON_SAVE = (
    "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'>"
    "<path fill='%23000' d='M7 1h2v6.2h2.6L8 11.2 4.4 7.2H7zM2.5 12.2h11V15h-11z'/></svg>"
)
_ICON_DOC = (
    "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'>"
    "<path fill='%23000' d='M3.5 1.2h6.2L13.5 5v9.8h-10zM9.2 1.6V5.4h3.6z'/></svg>"
)
_ICON_GEAR = (
    "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'>"
    "<path fill='%23000' fill-rule='evenodd' d='M7.1 0h1.8v2.1h-1.8zM7.1 13.9h1.8V16h-1.8z"
    "M0 7.1h2.1v1.8H0zm13.9 0H16v1.8h-2.1zM8 2.7a5.3 5.3 0 1 0 0 10.6 5.3 5.3 0 0 0 0-10.6z"
    "m0 2.6a2.7 2.7 0 1 1 0 5.4 2.7 2.7 0 0 1 0-5.4z'/></svg>"
)


def home_flag_css() -> str:
    """Shell overrides. They apply only while the Home marker is mounted."""
    icons = (
        (1, _ICON_HOME),
        (2, _ICON_WAVE),
        (3, _ICON_SAVE),
        (4, _ICON_DOC),
        (5, _ICON_GEAR),
    )
    icon_rules = "\n".join(
        "  .stApp:has(.att-home-v2) [data-testid='stSidebarNav'] li:nth-child("
        f"{index}) a {{ --att-nav-icon: {_mask(svg)}; }}"
        for index, svg in icons
    )
    return f"""
  .stApp:has(.att-home-v2),
  .stApp:has(.att-home-v2) [data-testid="stAppViewContainer"],
  .stApp:has(.att-home-v2) [data-testid="stMain"],
  .stApp:has(.att-home-v2) [data-testid="stMainBlockContainer"] {{
    background: {HOME_BG} !important;
  }}
  .stApp:has(.att-home-v2) [data-testid="stHeader"] {{
    display: none !important;
    height: 0 !important;
    min-height: 0 !important;
  }}
  .stApp:has(.att-home-v2) [data-testid="stMain"] {{
    height: 100vh !important;
    overflow: hidden !important;
  }}
  .stApp:has(.att-home-v2) [data-testid="stMainBlockContainer"],
  .stApp:has(.att-home-v2) [data-testid="stVerticalBlock"] {{
    height: 100% !important;
    max-width: none !important;
    padding: 0 !important;
    margin: 0 !important;
    gap: 0 !important;
  }}
  .stApp:has(.att-home-v2) [data-testid="stElementContainer"]:has([data-testid="stHtml"]) {{
    height: 0 !important;
    min-height: 0 !important;
    flex: 0 0 0px !important;
    overflow: hidden !important;
    padding: 0 !important;
    margin: 0 !important;
  }}
  .stApp:has(.att-home-v2) [data-testid="stElementContainer"]:has([data-testid="stCustomComponentV1"]),
  .stApp:has(.att-home-v2) [data-testid="stElementContainer"]:has(iframe) > div,
  .stApp:has(.att-home-v2) [data-testid="stCustomComponentV1"] {{
    height: 100% !important;
    min-height: 0 !important;
    flex: 1 1 auto !important;
    max-width: none !important;
    padding: 0 !important;
    margin: 0 !important;
  }}
  .stApp:has(.att-home-v2) [data-testid="stMain"] .block-container {{
    max-width: none !important;
    padding: 0 !important;
  }}
  .stApp:has(.att-home-v2) iframe {{
    display: block !important;
    width: 100% !important;
    height: 100% !important;
    min-height: 0 !important;
    border: 0 !important;
  }}
  .stApp:has(.att-home-v2) [data-testid="stSidebar"] {{
    position: relative !important;
    width: 240px !important;
    min-width: 240px !important;
    max-width: 240px !important;
    background: {HOME_BG} !important;
    color: {HOME_TEXT_SECONDARY} !important;
  }}
  .stApp:has(.att-home-v2) [data-testid="stSidebar"][aria-expanded="false"] {{
    width: 0 !important;
    min-width: 0 !important;
    max-width: 0 !important;
  }}
  .att-home-lockup {{
    position: fixed;
    top: 26px;
    left: 24px;
    width: 113px;
    height: 32px;
    display: flex;
    align-items: center;
    gap: 8px;
    overflow: hidden;
    z-index: 6;
    color: {HOME_WORDMARK};
    text-decoration: none;
  }}
  .att-home-lockup .mark {{
    width: 32px;
    height: 17px;
    display: flex;
    align-items: center;
    justify-content: center;
    flex: 0 0 32px;
  }}
  .att-home-lockup img {{
    width: 16px;
    height: 16px;
    display: block;
  }}
  .att-home-lockup .word {{
    font-size: 14px;
    line-height: 20px;
    font-weight: 500;
    letter-spacing: 0;
    color: {HOME_WORDMARK};
    white-space: nowrap;
  }}
  .stApp:has(.att-home-v2) [data-testid="stSidebarCollapseButton"],
  .stApp:has(.att-home-v2) [data-testid="stSidebarCollapsedControl"] {{
    position: absolute !important;
    top: 30px !important;
    left: 196px !important;
    width: 24px !important;
    height: 24px !important;
    z-index: 7 !important;
    visibility: visible !important;
  }}
  .stApp:has(.att-home-v2) [data-testid="stSidebarCollapseButton"] button,
  .stApp:has(.att-home-v2) [data-testid="stExpandSidebarButton"] button {{
    width: 24px !important;
    height: 24px !important;
    min-height: 24px !important;
    padding: 0 !important;
    background: transparent !important;
    color: {HOME_TEXT} !important;
  }}
  .stApp:has(.att-home-v2) [data-testid="stSidebarCollapseButton"] [data-testid="stIconMaterial"],
  .stApp:has(.att-home-v2) [data-testid="stExpandSidebarButton"] [data-testid="stIconMaterial"] {{
    font-size: 16px !important;
  }}
  .stApp:has(.att-home-v2) [data-testid="stSidebarContent"] {{
    padding-left: 0 !important;
    padding-right: 0 !important;
  }}
  .stApp:has(.att-home-v2) [data-testid="stSidebarHeader"] {{
    height: 0 !important;
    min-height: 0 !important;
    margin: 0 !important;
    overflow: visible !important;
  }}
  .stApp:has(.att-home-v2) [data-testid="stSidebarNav"] {{
    padding-top: 72px !important;
    margin-top: 0 !important;
  }}
  .stApp:has([data-testid="stSidebar"][aria-expanded="false"]) .att-home-lockup {{
    display: none !important;
  }}
  .stApp:has(.att-home-v2) [data-testid="stSidebarNav"] a {{
    width: 216px !important;
    height: 36px !important;
    min-height: 36px !important;
    margin: 0 0 0 12px !important;
    padding: 8px 12px !important;
    border-radius: 6px !important;
    display: flex !important;
    align-items: center !important;
    gap: 12px !important;
    box-sizing: border-box !important;
    font-size: 14px !important;
    line-height: 20px !important;
    font-weight: 400 !important;
    color: {HOME_TEXT_SECONDARY} !important;
    background: transparent !important;
    transition: background-color 0.2s ease, color 0.28s cubic-bezier(0.4, 0, 0.2, 1) !important;
  }}
  .stApp:has(.att-home-v2) [data-testid="stSidebarNav"] a span {{
    font-weight: 400 !important;
  }}
  .stApp:has(.att-home-v2) [data-testid="stSidebarNav"] a::before {{
    content: "";
    width: 16px;
    height: 16px;
    flex: 0 0 16px;
    background-color: {HOME_TEXT_SECONDARY};
    -webkit-mask: var(--att-nav-icon) center / 16px 16px no-repeat;
    mask: var(--att-nav-icon) center / 16px 16px no-repeat;
  }}
  .stApp:has(.att-home-v2) [data-testid="stSidebarNav"] a[aria-current="page"] {{
    background: {HOME_WASH} !important;
    color: {HOME_TEXT} !important;
    font-weight: 400 !important;
  }}
  .stApp:has(.att-home-v2) [data-testid="stSidebarNav"] a[aria-current="page"]::before {{
    background-color: #ffffff;
  }}
  .stApp:has(.att-home-v2) [data-testid="stSidebarNav"] a:hover {{
    background: {HOME_WASH_HOVER} !important;
  }}
  .stApp:has(.att-home-v2) [data-testid="stSidebarNav"] a:focus-visible,
  .stApp:has(.att-home-v2) [data-testid="stSidebarCollapseButton"] button:focus-visible,
  .stApp:has(.att-home-v2) [data-testid="stExpandSidebarButton"] button:focus-visible {{
    outline: 2px solid {HOME_LINE} !important;
    outline-offset: 2px !important;
  }}
  .stApp:has(.att-home-v2) [data-testid="stSidebar"] [data-testid="stWidgetLabel"] p {{
    color: {HOME_TEXT_MUTED} !important;
    font-size: 12px !important;
    line-height: 16px !important;
    font-weight: 500 !important;
    letter-spacing: 1.5px !important;
    text-transform: uppercase !important;
  }}
  .stApp:has(.att-home-v2) [data-testid="stSidebar"] [data-testid="stCaptionContainer"] p {{
    color: {HOME_TEXT_META} !important;
    font-size: 12px !important;
    line-height: 16px !important;
    font-weight: 400 !important;
    letter-spacing: 0.03px !important;
    text-transform: none !important;
  }}
  .stApp:has(.att-home-v2) [data-testid="stSidebar"] button:active {{
    transform: none !important;
  }}
{icon_rules}
  @media (prefers-reduced-motion: reduce) {{
    .stApp:has(.att-home-v2) [data-testid="stSidebarNav"] a {{
      transition-duration: 0ms !important;
    }}
  }}
"""
