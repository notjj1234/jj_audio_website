// web/src/components/ColorPicker.tsx
import { useState, forwardRef } from 'react';

interface ColorPickerProps {
  label: string;
  value: string;
  onChange: (value: string) => void;
  defaultValue: string;
}

export const ColorPicker = forwardRef<HTMLDivElement, ColorPickerProps>(
  ({ label, value, onChange, defaultValue }, _ref) => {
    const [hex, setHex] = useState(value || defaultValue);
    
    const handleInput = (e: React.ChangeEvent<HTMLInputElement>) => {
      const val = e.target.value;
      setHex(val);
      onChange(val);
    };
    
    const handleColorChange = (e: React.ChangeEvent<HTMLInputElement>) => {
      const val = e.target.value;
      setHex(val);
      onChange(val);
    };

    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.2rem' }}>
        <label style={{ fontSize: '0.7rem', color: 'var(--color-text-secondary)', fontWeight: 500 }}>{label}</label>
        <div style={{ display: 'flex', gap: '0.35rem', alignItems: 'center' }}>
          <input
            type="color"
            value={hex}
            onChange={handleColorChange}
            style={{ width: '32px', height: '32px', border: 'none', borderRadius: '4px', cursor: 'pointer', padding: 0 }}
            aria-label={label}
          />
          <input
            type="text"
            value={hex}
            onChange={handleInput}
            style={{
              flex: 1,
              padding: '0.35rem 0.5rem',
              border: '1px solid var(--color-border-subtle)',
              borderRadius: '4px',
              background: 'var(--color-bg-deep)',
              color: 'var(--color-text-primary)',
              fontSize: '0.75rem',
              fontFamily: 'monospace',
              textTransform: 'uppercase'
            }}
            placeholder={defaultValue}
            aria-label={`${label} hex value`}
          />
        </div>
      </div>
    );
  }
);

ColorPicker.displayName = 'ColorPicker';