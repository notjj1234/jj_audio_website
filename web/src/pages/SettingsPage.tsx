// web/src/pages/SettingsPage.tsx
import { ThemeSelector } from '../components/ThemeSelector';

export function SettingsPage() {
  return (
    <div style={{ maxWidth: '800px', margin: '0 auto', padding: '1.5rem' }}>
      <h1 style={{ marginBottom: '1.5rem' }}>Settings</h1>
      <ThemeSelector />
    </div>
  );
}