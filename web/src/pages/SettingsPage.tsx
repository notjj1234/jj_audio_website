import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import * as api from "../api";
import { useAuth } from "../auth";
import { ThemeSelector } from "../components/ThemeSelector";
import { LEGAL_PLACEHOLDERS } from "../legal/placeholders";

export function SettingsPage() {
  const { email, logout } = useAuth();
  const navigate = useNavigate();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [confirm, setConfirm] = useState("");

  async function onDelete() {
    if (confirm !== "DELETE") {
      setError("Type DELETE to confirm.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await api.deleteAccount();
      await logout();
      navigate("/login");
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="settings-page">
      <h1>Settings</h1>
      <ThemeSelector />

      <section className="settings-section" aria-labelledby="account-data-heading">
        <h2 id="account-data-heading" className="section-heading">
          Account &amp; data
        </h2>
        <p className="hint">
          Signed in as <strong>{email ?? "Anonymous session"}</strong>. Deleting
          removes your user row, uploads, and job artifacts from this demo
          environment. Admin accounts cannot self-delete via the API.
        </p>
        <label className="field">
          Type DELETE to confirm
          <input
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
            autoComplete="off"
            aria-describedby="delete-help"
          />
        </label>
        <p id="delete-help" className="hint">
          This cannot be undone for this demo database.
        </p>
        {error && <p className="error">{error}</p>}
        <button
          type="button"
          className="danger"
          disabled={busy || confirm !== "DELETE"}
          onClick={() => void onDelete()}
        >
          {busy ? "Deleting…" : "Delete my account & data"}
        </button>
      </section>

      <section className="settings-section" aria-labelledby="legal-heading">
        <h2 id="legal-heading" className="section-heading">
          Legal
        </h2>
        <p className="hint">Demo draft · not legal advice</p>
        <p className="hint">
          <a href={`mailto:${LEGAL_PLACEHOLDERS.contactEmail}`}>
            {LEGAL_PLACEHOLDERS.contactEmail}
          </a>
          {" · "}
          <Link to="/legal/privacy">View policies</Link>
        </p>
      </section>
    </div>
  );
}
