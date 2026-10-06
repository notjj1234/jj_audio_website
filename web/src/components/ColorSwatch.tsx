// web/src/components/ColorSwatch.tsx
interface ColorSwatchProps {
  color: string;
  label: string;
}

export function ColorSwatch({ color, label }: ColorSwatchProps) {
  return (
    <div 
      style={{ 
        width: '16px', 
        height: '16px', 
        borderRadius: '3px', 
        background: color, 
        border: '1px solid var(--color-border-subtle)' 
      }} 
      title={`${label}: ${color}`} 
    />
  );
}