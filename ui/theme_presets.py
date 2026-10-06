"""ui/theme_presets.py — Theme presets for desktop app (Streamlit)

Mirrors src/theme-presets.ts — keep in sync when adding/removing presets.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

AccentId = Literal['forest', 'teal', 'purple-gold', 'ocean', 'tyrian', 'custom']
ThemeMode = Literal['light', 'dark', 'system']

@dataclass(frozen=True)
class ThemePreset:
    id: str
    label: str
    description: str
    accent_id: AccentId
    is_colorblind_safe: bool
    preview: dict[str, str]  # primary, secondary, bg, text

THEME_PRESETS: tuple[ThemePreset, ...] = (
    ThemePreset(
        id='forest-dark',
        label='Forest Dark',
        description='Original brand — deep greens, warm sand accents',
        accent_id='forest',
        is_colorblind_safe=False,
        preview={'primary': '#2f6b4f', 'secondary': '#d4c4a8', 'bg': '#0a0f0a', 'text': '#e8efe6'}
    ),
    ThemePreset(
        id='forest-light',
        label='Forest Light',
        description='Light variant of the original brand',
        accent_id='forest',
        is_colorblind_safe=False,
        preview={'primary': '#2f6b4f', 'secondary': '#d4c4a8', 'bg': '#f0f2f5', 'text': '#1a1f1c'}
    ),
    ThemePreset(
        id='studio-teal-dark',
        label='Studio Teal (Dark)',
        description='Industry standard — teal primary, gold warnings. Used by Waves, NI.',
        accent_id='teal',
        is_colorblind_safe=True,
        preview={'primary': '#4ecdc4', 'secondary': '#ffcc53', 'bg': '#0a0f0a', 'text': '#e8efe6'}
    ),
ThemePreset(
            id='studio-teal-light',
            label='Studio Teal (Light)',
            description='Light variant of studio teal',
            accent_id='teal',
            is_colorblind_safe=True,
            preview={'primary': '#3aa8a0', 'secondary': '#e6b84a', 'bg': '#f0f2f5', 'text': '#1a1f1c'}
        ),
    ThemePreset(
        id='purple-gold-dark',
        label='Purple/Gold (Colorblind-Safe)',
        description='Maximum accessibility — distinguishable by all colorblind types',
        accent_id='purple-gold',
        is_colorblind_safe=True,
        preview={'primary': '#8b5cf6', 'secondary': '#fbbf24', 'bg': '#0a0f0a', 'text': '#e8efe6'}
    ),
    ThemePreset(
        id='purple-gold-light',
        label='Purple/Gold (Light)',
        description='Light variant of accessible purple/gold',
        accent_id='purple-gold',
        is_colorblind_safe=True,
        preview={'primary': '#7c3aed', 'secondary': '#f59e0b', 'bg': '#f0f2f5', 'text': '#1a1f1c'}
    ),
    ThemePreset(
        id='ocean-dark',
        label='Ocean Blue (Dark)',
        description='Blue primary — high contrast, calm studio aesthetic',
        accent_id='ocean',
        is_colorblind_safe=True,
        preview={'primary': '#0ea5e9', 'secondary': '#fbbf24', 'bg': '#0a0f0a', 'text': '#e8efe6'}
    ),
    ThemePreset(
        id='tyrian',
        label='Tyrian',
        description='Dark Tyrian blue and yellow-orange',
        accent_id='tyrian',
        is_colorblind_safe=False,
        preview={'primary': '#f6ad49', 'secondary': '#192542', 'bg': '#192542', 'text': '#f6ad49'},
    ),
    ThemePreset(
        id='custom',
        label='Custom Theme',
        description='Build your own — full control over every color',
        accent_id='custom',
        is_colorblind_safe=False,
        preview={'primary': '#2f6b4f', 'secondary': '#d4c4a8', 'bg': '#0a0f0a', 'text': '#e8efe6'}
    ),
)

DEFAULT_PRESET_ID = 'tyrian'

# Dark Tyrian blue #192542 and yellow-orange #f6ad49.
# Raised blue is Tyrian mixed toward white. Hover is the alternate yellow-orange.
TYRIAN_BLUE = '#192542'
TYRIAN_BLUE_RAISED = '#2A4467'
YELLOW_ORANGE = '#f6ad49'
YELLOW_ORANGE_HOVER = '#FFAB0F'
YELLOW_ORANGE_WASH = '#FFF6DC'

# CSS custom property definitions for each accent preset
ACCENT_TOKENS: dict[AccentId, dict[str, str]] = {
    'forest': {
        '--color-accent-primary': '#2f6b4f',
        '--color-accent-primary-hover': '#255840',
        '--color-accent-secondary': '#d4c4a8',
        '--color-accent-secondary-hover': '#c4b498',
        '--color-accent-tertiary': '#1e4533',
        '--color-accent-tertiary-hover': '#163626',
    },
    'teal': {
        '--color-accent-primary': '#4ecdc4',
        '--color-accent-primary-hover': '#3abdb4',
        '--color-accent-secondary': '#ffcc53',
        '--color-accent-secondary-hover': '#e6b84a',
        '--color-accent-tertiary': '#3aa8a0',
        '--color-accent-tertiary-hover': '#2f8f87',
    },
    'purple-gold': {
        '--color-accent-primary': '#8b5cf6',
        '--color-accent-primary-hover': '#7c3aed',
        '--color-accent-secondary': '#fbbf24',
        '--color-accent-secondary-hover': '#f59e0b',
        '--color-accent-tertiary': '#a855f7',
        '--color-accent-tertiary-hover': '#9333ea',
    },
    'ocean': {
        '--color-accent-primary': '#0ea5e9',
        '--color-accent-primary-hover': '#0284c7',
        '--color-accent-secondary': '#fbbf24',
        '--color-accent-secondary-hover': '#f59e0b',
        '--color-accent-tertiary': '#0369a1',
        '--color-accent-tertiary-hover': '#075985',
    },
    'tyrian': {
        '--color-accent-primary': YELLOW_ORANGE,
        '--color-accent-primary-hover': YELLOW_ORANGE_HOVER,
        '--color-accent-secondary': YELLOW_ORANGE,
        '--color-accent-secondary-hover': YELLOW_ORANGE_HOVER,
        '--color-accent-tertiary': TYRIAN_BLUE,
        '--color-accent-tertiary-hover': TYRIAN_BLUE_RAISED,
    },
    'custom': {},  # Populated dynamically from user custom tokens
}

TYRIAN_BASE_DARK: dict[str, str] = {
    '--color-bg-deepest': TYRIAN_BLUE,
    '--color-bg-deep': TYRIAN_BLUE,
    '--color-bg-raised': TYRIAN_BLUE_RAISED,
    '--color-bg-highlight': TYRIAN_BLUE_RAISED,
    '--color-text-primary': YELLOW_ORANGE,
    '--color-text-secondary': YELLOW_ORANGE,
    '--color-text-muted': YELLOW_ORANGE_HOVER,
    '--color-border-subtle': 'rgba(246, 173, 73, 0.35)',
    '--color-link': YELLOW_ORANGE,
    '--color-waveform-bg': TYRIAN_BLUE,
}

TYRIAN_BASE_LIGHT: dict[str, str] = {
    '--color-bg-deepest': YELLOW_ORANGE_WASH,
    '--color-bg-deep': YELLOW_ORANGE_WASH,
    '--color-bg-raised': '#FFFFFF',
    '--color-bg-highlight': '#E7EDF6',
    '--color-text-primary': TYRIAN_BLUE,
    '--color-text-secondary': TYRIAN_BLUE,
    '--color-text-muted': TYRIAN_BLUE_RAISED,
    '--color-border-subtle': 'rgba(25, 37, 66, 0.22)',
    '--color-waveform-bg': YELLOW_ORANGE_WASH,
    '--color-link': TYRIAN_BLUE,
}

# Base layer tokens (dark/light)
BASE_TOKENS_DARK: dict[str, str] = {
    '--color-bg-deepest': '#0a0f0a',
    '--color-bg-deep': '#141a14',
    '--color-bg-raised': '#1e261e',
    '--color-bg-highlight': '#2a342a',
    '--color-text-primary': '#e8efe6',
    '--color-text-secondary': '#9aa0a6',
    '--color-text-muted': '#5f6368',
    '--color-border-subtle': 'rgba(232, 239, 230, 0.08)',
    '--color-waveform-bg': '#0f150f',
}

BASE_TOKENS_LIGHT: dict[str, str] = {
    '--color-bg-deepest': '#f0f2f5',
    '--color-bg-deep': '#e4e7eb',
    '--color-bg-raised': '#ffffff',
    '--color-bg-highlight': '#f7f8fa',
    '--color-text-primary': '#1a1f1c',
    '--color-text-secondary': '#5f6368',
    '--color-text-muted': '#9aa0a6',
    '--color-border-subtle': 'rgba(26, 31, 28, 0.1)',
    '--color-waveform-bg': '#e8efe6',
}

# Semantic signals (always same — colorblind-safe)
SIGNAL_TOKENS: dict[str, str] = {
    '--color-signal-low': '#4ecdc4',
    '--color-signal-mid': '#ffcc53',
    '--color-signal-high': '#ff6b6b',
    '--color-danger': '#e85d5d',
}

def get_preset_by_id(preset_id: str) -> ThemePreset:
    """Find preset by id, fallback to the Tyrian default."""
    for preset in THEME_PRESETS:
        if preset.id == preset_id:
            return preset
    for preset in THEME_PRESETS:
        if preset.id == DEFAULT_PRESET_ID:
            return preset
    return THEME_PRESETS[0]

def get_accent_tokens(accent_id: AccentId, custom_tokens: dict[str, str] | None = None) -> dict[str, str]:
    """Get accent tokens for a preset, with custom overrides."""
    if accent_id == 'custom' and custom_tokens:
        # Custom tokens use --custom- prefix for base layers, direct for accents
        result = {}
        for key, value in custom_tokens.items():
            if key.startswith('--custom-'):
                # Map --custom-bg-deepest -> --color-bg-deepest etc.
                mapped_key = key.replace('--custom-', '--color-')
                result[mapped_key] = value
            elif key.startswith('--color-'):
                result[key] = value
        return result
    return ACCENT_TOKENS.get(accent_id, ACCENT_TOKENS['forest'])

def get_base_tokens(mode: ThemeMode) -> dict[str, str]:
    """Get base layer tokens for a theme mode."""
    if mode == 'light':
        return BASE_TOKENS_LIGHT
    return BASE_TOKENS_DARK

def build_all_tokens(
    preset_id: str,
    mode: ThemeMode,
    custom_tokens: dict[str, str] | None = None
) -> dict[str, str]:
    """Build complete token set for injection."""
    preset = get_preset_by_id(preset_id)
    if preset.accent_id == "tyrian":
        base = TYRIAN_BASE_LIGHT if mode == "light" else TYRIAN_BASE_DARK
        return {**base, **get_accent_tokens("tyrian", custom_tokens)}
    base = get_base_tokens(mode)
    accent = get_accent_tokens(preset.accent_id, custom_tokens)
    
    # Merge: base first, then accent (accent can override), then signals
    return {**base, **accent, **SIGNAL_TOKENS}