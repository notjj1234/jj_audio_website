// src/theme-presets.ts — Theme preset registry for web (React)
/* Mirrors ui/theme_presets.py — keep in sync */

export type AccentId = 'forest' | 'teal' | 'purple-gold' | 'ocean' | 'custom';
export type ThemeMode = 'light' | 'dark' | 'system';

export interface ThemePreset {
  id: string;
  label: string;
  description: string;
  accentId: AccentId;
  isColorblindSafe: boolean;
  preview: {
    primary: string;
    secondary: string;
    bg: string;
    text: string;
  };
}

export const THEME_PRESETS: readonly ThemePreset[] = [
  {
    id: 'forest-dark',
    label: 'Forest Dark',
    description: 'Original brand — deep greens, warm sand accents',
    accentId: 'forest',
    isColorblindSafe: false,
    preview: { primary: '#2f6b4f', secondary: '#d4c4a8', bg: '#0a0f0a', text: '#e8efe6' }
  },
  {
    id: 'forest-light',
    label: 'Forest Light',
    description: 'Light variant of the original brand',
    accentId: 'forest',
    isColorblindSafe: false,
    preview: { primary: '#2f6b4f', secondary: '#d4c4a8', bg: '#f0f2f5', text: '#1a1f1c' }
  },
  {
    id: 'studio-teal-dark',
    label: 'Studio Teal (Dark)',
    description: 'Industry standard — teal primary, gold warnings. Used by Waves, NI.',
    accentId: 'teal',
    isColorblindSafe: true,
    preview: { primary: '#4ecdc4', secondary: '#ffcc53', bg: '#0a0f0a', text: '#e8efe6' }
  },
  {
    id: 'studio-teal-light',
    label: 'Studio Teal (Light)',
    description: 'Light variant of studio teal',
    accentId: 'teal',
    isColorblindSafe: true,
    preview: { primary: '#3aa8a0', secondary: '#e6b84a', bg: '#f0f2f5', text: '#1a1f1c' }
  },
  {
    id: 'purple-gold-dark',
    label: 'Purple/Gold (Colorblind-Safe)',
    description: 'Maximum accessibility — distinguishable by all colorblind types',
    accentId: 'purple-gold',
    isColorblindSafe: true,
    preview: { primary: '#8b5cf6', secondary: '#fbbf24', bg: '#0a0f0a', text: '#e8efe6' }
  },
  {
    id: 'purple-gold-light',
    label: 'Purple/Gold (Light)',
    description: 'Light variant of accessible purple/gold',
    accentId: 'purple-gold',
    isColorblindSafe: true,
    preview: { primary: '#7c3aed', secondary: '#f59e0b', bg: '#f0f2f5', text: '#1a1f1c' }
  },
  {
    id: 'ocean-dark',
    label: 'Ocean Blue (Dark)',
    description: 'Blue primary — high contrast, calm studio aesthetic',
    accentId: 'ocean',
    isColorblindSafe: true,
    preview: { primary: '#0ea5e9', secondary: '#fbbf24', bg: '#0a0f0a', text: '#e8efe6' }
  },
  {
    id: 'custom',
    label: 'Custom Theme',
    description: 'Build your own — full control over every color',
    accentId: 'custom',
    isColorblindSafe: false,
    preview: { primary: '#2f6b4f', secondary: '#d4c4a8', bg: '#0a0f0a', text: '#e8efe6' }
  },
] as const;

export const DEFAULT_PRESET_ID = 'forest-dark';

export function getPresetById(id: string): ThemePreset {
  return THEME_PRESETS.find(p => p.id === id) ?? THEME_PRESETS[0];
}

export function getPresetsByAccent(accentId: AccentId): ThemePreset[] {
  return THEME_PRESETS.filter(p => p.accentId === accentId);
}

export function getColorblindSafePresets(): ThemePreset[] {
  return THEME_PRESETS.filter(p => p.isColorblindSafe);
}