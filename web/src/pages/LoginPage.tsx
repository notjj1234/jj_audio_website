import { useState, type FormEvent } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import { useAuth } from "../auth";

export function LoginPage() {
  const { email, loading, login } = useAuth();
  const navigate = useNavigate();
  const [user, setUser] = useState("admin@localhost");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  if (!loading && email) return <Navigate to="/tab" replace />;

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await login(user, password);
      navigate("/tab");
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
        Sign in to turn tracks into guitar tabs or isolate stems — built for real
        async jobs, not a laptop demo.
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
        {error && <p className="error">{error}</p>}
        <button type="submit" disabled={busy}>
          {busy ? "Signing in…" : "Sign in"}
        </button>
      </form>
    </div>
  );
}
