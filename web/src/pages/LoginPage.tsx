import { useState, type FormEvent } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { useAuth } from "../auth";

export function LoginPage() {
  const { email, loading, login } = useAuth();
  const navigate = useNavigate();
  const [user, setUser] = useState("admin@localhost");
  const [password, setPassword] = useState("");
  const [acceptTerms, setAcceptTerms] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  if (!loading && email) return <Navigate to="/isolate" replace />;

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!acceptTerms) {
      setError("Confirm you accept the Terms and Privacy policy.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await login(user, password);
      navigate("/isolate");
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="login-hero">
      <p className="brand-hero">Audio Tools</p>
      <p className="lede">
        Sign in to try stem isolation and Tab PDF on the hosted demo. This is an
        unfinished product — results can be wrong. Processing uses your uploads
        and account email as described in the Privacy policy.
      </p>
      <form className="stack" onSubmit={onSubmit}>
        <label className="field">
          Email
          <input
            type="email"
            value={user}
            onChange={(e) => setUser(e.target.value)}
            required
            autoComplete="username"
          />
        </label>
        <label className="field">
          Password
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            autoComplete="current-password"
          />
        </label>
        <label className="consent-check">
          <input
            type="checkbox"
            checked={acceptTerms}
            onChange={(e) => setAcceptTerms(e.target.checked)}
          />
          <span>
            I agree to the <Link to="/legal/terms">Terms</Link> and{" "}
            <Link to="/legal/privacy">Privacy policy</Link>.
          </span>
        </label>
        {error && <p className="error">{error}</p>}
        <button type="submit" disabled={busy || !acceptTerms}>
          {busy ? "Signing in…" : "Sign in"}
        </button>
      </form>
    </div>
  );
}
