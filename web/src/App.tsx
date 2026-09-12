import { NavLink, Navigate, Outlet, Route, Routes } from "react-router-dom";
import { AuthProvider, useAuth } from "./auth";
import { IsolatePage } from "./pages/IsolatePage";
import { TabPage } from "./pages/TabPage";

function Shell() {
  const { loading, sessionError, retrySession } = useAuth();

  if (loading) {
    return (
      <main>
        <p>Loading…</p>
      </main>
    );
  }

  if (sessionError) {
    return (
      <main>
        <p className="error">{sessionError}</p>
        <p className="hint">Could not start a session. Check that the API is running, then retry.</p>
        <button type="button" onClick={() => void retrySession()}>
          Retry
        </button>
      </main>
    );
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <NavLink to="/isolate" className="brand">
          Audio Tools
        </NavLink>
        <nav className="nav">
          <NavLink to="/tab" className={({ isActive }) => (isActive ? "active" : "")}>
            Tab PDF
          </NavLink>
          <NavLink
            to="/isolate"
            className={({ isActive }) => (isActive ? "active" : "")}
          >
            Isolate
          </NavLink>
          <a
            href="https://github.com/notjj1234/jj_audio_website/issues"
            target="_blank"
            rel="noopener noreferrer"
          >
            Send feedback
          </a>
        </nav>
      </header>
      <main>
        <Outlet />
      </main>
    </div>
  );
}

export function App() {
  return (
    <AuthProvider>
      <Routes>
        <Route element={<Shell />}>
          <Route path="/tab" element={<TabPage />} />
          <Route path="/isolate" element={<IsolatePage />} />
          <Route path="*" element={<Navigate to="/isolate" replace />} />
        </Route>
      </Routes>
    </AuthProvider>
  );
}
