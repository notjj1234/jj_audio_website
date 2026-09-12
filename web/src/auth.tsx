import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import * as api from "./api";

type AuthState = {
  email: string | null;
  loading: boolean;
  sessionError: string | null;
  retrySession: () => Promise<void>;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
};

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [email, setEmail] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [sessionError, setSessionError] = useState<string | null>(null);

  const bootstrap = useCallback(async () => {
    setLoading(true);
    setSessionError(null);
    const token = api.getAccessToken();
    if (token) {
      try {
        const u = await api.me();
        setEmail(u.email);
        setLoading(false);
        return;
      } catch {
        api.setAccessToken(null);
      }
    }
    try {
      const res = await api.startAnonymousSession();
      setEmail(res.email);
    } catch (err) {
      setEmail(null);
      setSessionError(
        err instanceof Error ? err.message : "Could not start a session."
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void bootstrap();
  }, [bootstrap]);

  const login = useCallback(async (e: string, password: string) => {
    const res = await api.login(e, password);
    setEmail(res.email);
    setSessionError(null);
  }, []);

  const logout = useCallback(async () => {
    await api.logout();
    setEmail(null);
  }, []);

  return (
    <AuthContext.Provider
      value={{
        email,
        loading,
        sessionError,
        retrySession: bootstrap,
        login,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth outside AuthProvider");
  return ctx;
}
