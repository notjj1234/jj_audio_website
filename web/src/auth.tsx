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
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
};

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [email, setEmail] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = api.getAccessToken();
    if (token) {
      api
        .me()
        .then((u) => setEmail(u.email))
        .catch(() => api.setAccessToken(null))
        .finally(() => setLoading(false));
      return;
    }
    api
      .startAnonymousSession()
      .then((res) => setEmail(res.email))
      .catch(() => {
        /* demo session unavailable */
      })
      .finally(() => setLoading(false));
  }, []);

  const login = useCallback(async (e: string, password: string) => {
    const res = await api.login(e, password);
    setEmail(res.email);
  }, []);

  const logout = useCallback(async () => {
    await api.logout();
    setEmail(null);
  }, []);

  return (
    <AuthContext.Provider value={{ email, loading, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth outside AuthProvider");
  return ctx;
}
