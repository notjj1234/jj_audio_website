// web/src/components/ThemeSelector.tsx
import { useTheme } from '../theme/ThemeContext';
import { ColorSwatch } from './ColorSwatch';
import { ColorPicker } from './ColorPicker';
import { useState } from 'react';

const TOKEN_GROUPS = {
  'Base Layers': [
    { key: '--custom-bg-deepest', label: 'Deepest Background', default: '#0a0f0a' },
    { key: '--custom-bg-deep', label: 'Panel Background', default: '#141a14' },
    { key: '--custom-bg-raised', label: 'Raised/Hover Background', default: '#1e261e' },
    { key: '--custom-bg-highlight', label: 'Active/Highlight Background', default: '#2a342a' },
  ],
  'Text Colors': [
    { key: '--custom-text-primary', label: 'Primary Text', default: '#e8efe6' },
    { key: '--custom-text-secondary', label: 'Secondary Text', default: '#9aa0a6' },
    { key: '--custom-text-muted', label: 'Muted/Disabled Text', default: '#5f6368' },
  ],
  'Accent Colors': [
    { key: '--custom-accent-primary', label: 'Primary Accent (buttons, links)', default: '#2f6b4f' },
    { key: '--custom-accent-primary-hover', label: 'Primary Accent Hover', default: '#255840' },
    { key: '--custom-accent-secondary', label: 'Secondary Accent (warnings, solo)', default: '#d4c4a8' },
    { key: '--custom-accent-secondary-hover', label: 'Secondary Accent Hover', default: '#c4b498' },
    { key: '--custom-accent-tertiary', label: 'Tertiary Accent (borders, subtle)', default: '#1e4533' },
    { key: '--custom-accent-tertiary-hover', label: 'Tertiary Accent Hover', default: '#163626' },
  ],
} as const;

function CustomThemeBuilder({ customTokens, onChange, onReset }: { customTokens: Record<string, string>; onChange: (key: string, value: string) => void; onReset: () => void }) {
  const [expandedGroups, setExpandedGroups] = useState<string[]>(['Accent Colors']);

  const getValue = (key: string) => customTokens[key] ?? TOKEN_GROUPS[key as keyof typeof TOKEN_GROUPS]?.[0]?.default ?? '';

  const toggleGroup = (group: string) => {
    setExpandedGroups(prev => prev.includes(group) 
      ? prev.filter(g => g !== group) 
      : [...prev, group]
    );
  };

  return (
    <fieldset style={{ border: '1px solid var(--color-accent-primary)', borderRadius: '8px', padding: '0.75rem', background: 'rgba(47, 107, 79, 0.05)' }}>
      <legend style={{ fontWeight: 600, fontSize: '0.85rem', color: 'var(--color-accent-primary)' }}>
        Custom Theme Builder
      </legend>
      <p style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)', margin: '0 0 0.75rem' }}>
        Adjust any color. Changes apply instantly. <button type="button" onClick={onReset} style={{ color: 'var(--color-accent-primary)', background: 'none', border: 'none', textDecoration: 'underline', cursor: 'pointer' }}>Reset to preset</button>
      </p>
      
      {Object.entries(TOKEN_GROUPS).map(([groupName, tokens]) => (
        <div key={groupName} style={{ marginBottom: '0.75rem' }}>
          <button
            type="button"
            onClick={() => toggleGroup(groupName)}
            style={{
              width: '100%',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              padding: '0.5rem',
              background: 'transparent',
              border: 'none',
              color: 'var(--color-text-primary)',
              fontWeight: 600,
              fontSize: '0.8rem',
              cursor: 'pointer',
              textAlign: 'left'
            }}
          >
            {groupName}
            <span style={{ transform: expandedGroups.includes(groupName) ? 'rotate(180deg)' : 'rotate(0deg)', transition: 'transform 0.15s' }}>▼</span>
          </button>
          
          {expandedGroups.includes(groupName) && (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: '0.5rem', marginTop: '0.5rem', paddingLeft: '0.5rem' }}>
              {tokens.map(({ key, label, default: def }) => (
                <ColorPicker
                  key={key}
                  label={label}
                  value={getValue(key)}
                  onChange={(val) => onChange(key, val)}
                  defaultValue={def}
                />
              ))}
            </div>
          )}
        </div>
      ))}
      
      <div style={{ display: 'flex', gap: '0.5rem', justifyContent: 'flex-end', marginTop: '0.5rem' }}>
        <button type="button" onClick={onReset} style={{ padding: '0.5rem 1rem', borderRadius: '6px', border: '1px solid var(--color-border-subtle)', background: 'var(--color-bg-raised)', color: 'var(--color-text-primary)', fontWeight: 600, cursor: 'pointer' }}>
          Reset All
        </button>
        <button type="button" onClick={() => navigator.clipboard.writeText(JSON.stringify(customTokens, null, 2))} style={{ padding: '0.5rem 1rem', borderRadius: '6px', border: '1px solid var(--color-accent-primary)', background: 'var(--color-accent-primary)', color: '#fff', fontWeight: 600, cursor: 'pointer' }}>
          Export JSON
        </button>
        <input type="file" accept=".json" style={{ display: 'none' }} id="theme-import" onChange={e => {
          const file = e.target.files?.[0];
          if (file) {
            const reader = new FileReader();
            reader.onload = () => {
              try {
                const imported = JSON.parse(reader.result as string);
                Object.entries(imported).forEach(([k, v]) => onChange(k, v as string));
              } catch { alert('Invalid theme file'); }
            };
            reader.readAsText(file);
          }
        }} />
        <label htmlFor="theme-import" style={{ padding: '0.5rem 1rem', borderRadius: '6px', border: '1px solid var(--color-border-subtle)', background: 'var(--color-bg-raised)', color: 'var(--color-text-primary)', fontWeight: 600, cursor: 'pointer' }}>
          Import JSON
        </label>
      </div>
    </fieldset>
  );
}

export function ThemeSelector({ compact = false }: { compact?: boolean }) {
  const { presetId, mode, setPreset, setMode, availablePresets, currentPreset, customTokens, setCustomToken, resetCustomTokens } = useTheme();

  return (
    <div className="theme-selector" style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
      {/* Mode Toggle */}
      <fieldset style={{ border: '1px solid var(--color-border-subtle)', borderRadius: '8px', padding: '0.75rem' }}>
        <legend style={{ fontWeight: 600, fontSize: '0.85rem', color: 'var(--color-text-secondary)' }}>
          Theme Mode
        </legend>
        <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
          {(['light', 'dark', 'system'] as const).map(m => (
            <button
              key={m}
              type="button"
              onClick={() => setMode(m)}
              style={{
                padding: '0.5rem 1rem',
                borderRadius: '6px',
                border: `1px solid ${mode === m ? 'var(--color-accent-primary)' : 'var(--color-border-subtle)'}`,
                background: mode === m ? 'var(--color-accent-primary)' : 'var(--color-bg-raised)',
                color: mode === m ? '#fff' : 'var(--color-text-primary)',
                fontWeight: 600,
                cursor: 'pointer',
                fontSize: '0.85rem'
              }}
            >
              {m.charAt(0).toUpperCase() + m.slice(1)}
            </button>
          ))}
        </div>
      </fieldset>

      {/* Preset Grid */}
      <fieldset style={{ border: '1px solid var(--color-border-subtle)', borderRadius: '8px', padding: '0.75rem' }}>
        <legend style={{ fontWeight: 600, fontSize: '0.85rem', color: 'var(--color-text-secondary)' }}>
          Color Preset {currentPreset.isColorblindSafe && <span style={{ marginLeft: '0.5rem', fontSize: '0.7rem', background: 'var(--color-accent-secondary)', color: '#000', padding: '0.1rem 0.3rem', borderRadius: '4px' }}>♿ Colorblind-Safe</span>}
        </legend>
        <div style={{ display: 'grid', gridTemplateColumns: compact ? 'repeat(2, 1fr)' : 'repeat(4, 1fr)', gap: '0.5rem' }}>
          {availablePresets.map(preset => (
            <button
              key={preset.id}
              type="button"
              onClick={() => setPreset(preset.id)}
              style={{
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                gap: '0.35rem',
                padding: '0.75rem',
                borderRadius: '8px',
                border: `2px solid ${presetId === preset.id ? 'var(--color-accent-primary)' : 'var(--color-border-subtle)'}`,
                background: presetId === preset.id ? 'var(--color-bg-highlight)' : 'var(--color-bg-deep)',
                cursor: 'pointer',
                textAlign: 'center',
                transition: 'all 0.15s ease'
              }}
              title={preset.description}
            >
              <div style={{ display: 'flex', gap: '4px' }}>
                <ColorSwatch color={preset.preview.bg} label="BG" />
                <ColorSwatch color={preset.preview.primary} label="Primary" />
                <ColorSwatch color={preset.preview.secondary} label="Accent" />
                <ColorSwatch color={preset.preview.text} label="Text" />
              </div>
              <span style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--color-text-primary)' }}>{preset.label}</span>
              <span style={{ fontSize: '0.65rem', color: 'var(--color-text-muted)' }}>{preset.description}</span>
            </button>
          ))}
        </div>
      </fieldset>

      {/* Custom Theme Builder (when 'custom' selected) */}
      {presetId === 'custom' && (
        <CustomThemeBuilder customTokens={customTokens} onChange={setCustomToken} onReset={resetCustomTokens} />
      )}
    </div>
  );
}