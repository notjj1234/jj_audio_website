import type { ReactNode } from "react";
import { NavLink, Navigate, Outlet, Route, Routes } from "react-router-dom";
import { AuthProvider, useAuth } from "./auth";
import { IsolatePage } from "./pages/IsolatePage";
import { LoginPage } from "./pages/LoginPage";
import { TabPage } from "./pages/TabPage";

function Shell() {
  const { email, loading, logout } = useAuth();

  if (loading) {
    return (
      <main>
        <p>Loading…</p>
      </main>
    );
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <NavLink to={email ? "/isolate" : "/login"} className="brand">
          Audio Tools
        </NavLink>
        {email && (
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
            <span style={{ opacity: 0.7, fontSize: "0.9rem" }}>{email}</span>
            <button type="button" className="secondary" onClick={() => void logout()}>
              Log out
            </button>
          </nav>
        )}
      </header>
      <main>
        <Outlet />
      </main>
    </div>
  );
}

function RequireAuth({ children }: { children: ReactNode }) {
  const { email, loading } = useAuth();
  if (loading) return <p>Loading…</p>;
  if (!email) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

export function App() {
  return (
    <AuthProvider>
      <Routes>
        <Route element={<Shell />}>
          <Route path="/login" element={<LoginPage />} />
          <Route
            path="/tab"
            element={
              <RequireAuth>
                <TabPage />
              </RequireAuth>
            }
          />
          <Route
            path="/isolate"
            element={
              <RequireAuth>
                <IsolatePage />
              </RequireAuth>
            }
          />
          <Route path="*" element={<Navigate to="/isolate" replace />} />
        </Route>
      </Routes>
    </AuthProvider>
  );
}
