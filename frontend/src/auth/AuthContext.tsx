import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { api, onSessionExpired, tokens, type TokenPair } from "../api/client";

type Auth = {
  loggedIn: boolean;
  /** True when the user was logged out because the session couldn't be refreshed. */
  expired: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (body: { email: string; password: string; full_name?: string; shop_name: string }) => Promise<void>;
  logout: () => void;
};

const AuthContext = createContext<Auth | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const qc = useQueryClient();
  const [loggedIn, setLoggedIn] = useState(() => Boolean(tokens.refresh));
  const [expired, setExpired] = useState(false);

  useEffect(
    () =>
      onSessionExpired(() => {
        setLoggedIn(false);
        setExpired(true);
        qc.clear();
      }),
    [qc],
  );

  // Logging in or out in another tab
  useEffect(() => {
    const onStorage = (e: StorageEvent) => {
      if (e.key === null || e.key.startsWith("dm.")) setLoggedIn(Boolean(tokens.refresh));
    };
    window.addEventListener("storage", onStorage);
    return () => window.removeEventListener("storage", onStorage);
  }, []);

  const start = useCallback(
    (pair: TokenPair) => {
      qc.clear();
      tokens.set(pair);
      setExpired(false);
      setLoggedIn(true);
    },
    [qc],
  );

  const value = useMemo<Auth>(
    () => ({
      loggedIn,
      expired,
      login: async (email, password) =>
        start(await api<TokenPair>("/auth/login", { method: "POST", json: { email, password }, auth: false })),
      register: async (body) => start(await api<TokenPair>("/auth/register", { method: "POST", json: body, auth: false })),
      logout: () => {
        tokens.clear();
        setLoggedIn(false);
        setExpired(false);
        qc.clear();
      },
    }),
    [loggedIn, expired, start, qc],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): Auth {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth outside AuthProvider");
  return ctx;
}
