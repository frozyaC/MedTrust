import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from 'react';
import { apiBaseUrl, apiFetch, responseError } from '../api/client';

export interface AuthUser {
  id: string;
  login: string;
  name: string;
  role: 'registrar' | 'kb_owner';
}

interface AuthState {
  user: AuthUser | null;
  loading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
  login: (login: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthState | null>(null);

function clearUserStorage() {
  try {
    window.localStorage.removeItem('medtrust.auth');
    window.localStorage.removeItem('medtrust.conversationIds');
  } catch {
    // Session authentication also works when browser storage is unavailable.
  }
}

export function userInitials(name: string): string {
  return name.trim().split(/\s+/).slice(0, 2).map((part) => part[0]).join('').toUpperCase();
}

export function userRoleLabel(user: AuthUser): string {
  return user.role === 'kb_owner' ? 'Руководитель · владелец БЗ' : 'Регистратор';
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const identityRevision = useRef(0);
  const refreshRevision = useRef(0);

  const refresh = useCallback(async (background = false) => {
    const identity = identityRevision.current;
    const revision = ++refreshRevision.current;
    const isCurrent = () => identity === identityRevision.current && revision === refreshRevision.current;
    if (!background) setLoading(true);
    setError(null);
    try {
      const response = await apiFetch(`${apiBaseUrl()}/api/v1/auth/me`, {}, false);
      if (!isCurrent()) return;
      if (response.status === 401) {
        clearUserStorage();
        setUser(null);
      } else {
        if (!response.ok) throw await responseError(response);
        const currentUser = await response.json() as AuthUser;
        if (isCurrent()) setUser(currentUser);
      }
    } catch {
      if (isCurrent()) {
        setUser(null);
        setError('Не удалось проверить сессию. Проверьте соединение и повторите попытку.');
      }
    } finally {
      if (isCurrent()) setLoading(false);
    }
  }, []);

  useEffect(() => {
    const unauthorized = () => {
      identityRevision.current++;
      clearUserStorage();
      setUser(null);
      setError(null);
      setLoading(false);
    };
    const recheck = () => { void refresh(true); };
    window.addEventListener('medtrust:unauthorized', unauthorized);
    window.addEventListener('medtrust:forbidden', recheck);
    window.addEventListener('focus', recheck);
    void refresh();
    return () => {
      window.removeEventListener('medtrust:unauthorized', unauthorized);
      window.removeEventListener('medtrust:forbidden', recheck);
      window.removeEventListener('focus', recheck);
    };
  }, [refresh]);

  const login = async (login: string, password: string) => {
    const response = await apiFetch(`${apiBaseUrl()}/api/v1/auth/login`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ login, password }),
    }, false);
    if (!response.ok) throw await responseError(response);
    const currentUser = await response.json() as AuthUser;
    identityRevision.current++;
    clearUserStorage();
    setError(null);
    setLoading(false);
    setUser(currentUser);
  };

  const logout = async () => {
    const response = await apiFetch(`${apiBaseUrl()}/api/v1/auth/logout`, { method: 'POST' }, false);
    if (!response.ok) throw await responseError(response);
    identityRevision.current++;
    clearUserStorage();
    setUser(null);
    setError(null);
    setLoading(false);
  };

  return <AuthContext.Provider value={{ user, loading, error, refresh, login, logout }}>
    {children}
  </AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const context = useContext(AuthContext);
  if (!context) throw new Error('AuthProvider is required');
  return context;
}
