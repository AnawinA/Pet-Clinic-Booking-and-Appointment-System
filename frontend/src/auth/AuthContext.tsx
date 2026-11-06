import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { endpoints } from "../api/endpoints";
import { ApiError, tokenStore } from "../api/client";
import type { User, UserRole } from "../api/types";

interface AuthContextValue {
  user: User | null;
  token: string | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<User>;
  register: (payload: {
    email: string;
    password: string;
    full_name: string;
    phone?: string | null;
  }) => Promise<User>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function homeFor(role: UserRole): string {
  if (role === "OWNER") return "/owner/appointments";
  if (role === "VET") return "/vet/schedule";
  return "/staff/board";
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(() => tokenStore.get());
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(Boolean(tokenStore.get()));

  useEffect(() => {
    if (!token) {
      setUser(null);
      setLoading(false);
      return;
    }
    let active = true;
    setLoading(true);
    endpoints.auth
      .me()
      .then((profile) => {
        if (active) setUser(profile);
      })
      .catch((error: unknown) => {
        if (!active) return;
        // A full navigation can abort /auth/me. Only a real 401 should clear the session.
        if (error instanceof ApiError && error.status === 401) {
          tokenStore.set(null);
          setToken(null);
        }
        setUser(null);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [token]);

  useEffect(() => {
    const handleUnauthorized = () => {
      tokenStore.set(null);
      setToken(null);
      setUser(null);
    };
    window.addEventListener("petcare:unauthorized", handleUnauthorized);
    return () => window.removeEventListener("petcare:unauthorized", handleUnauthorized);
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const response = await endpoints.auth.login(email, password);
    tokenStore.set(response.access_token);
    setToken(response.access_token);
    setUser(response.user);
    return response.user;
  }, []);

  const register = useCallback(
    async (payload: {
      email: string;
      password: string;
      full_name: string;
      phone?: string | null;
    }) => {
      await endpoints.auth.register(payload);
      return login(payload.email, payload.password);
    },
    [login],
  );

  const logout = useCallback(() => {
    tokenStore.set(null);
    setToken(null);
    setUser(null);
  }, []);

  const value = useMemo(
    () => ({ user, token, loading, login, register, logout }),
    [user, token, loading, login, register, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used inside AuthProvider");
  return context;
}
