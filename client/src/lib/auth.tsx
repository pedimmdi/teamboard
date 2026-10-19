"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from "react";
import {
  getCurrentUser,
  logout as logoutApi,
  type CurrentUser,
  refreshToken,
} from "@/lib/api";

type AuthContextValue = {
  accessToken: string | null;
  user: CurrentUser | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  setTokens: (access: string, refresh: string) => void;
  logout: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | undefined>(
  undefined,
);

export function AuthProvider({
  children,
}: {
  children: React.ReactNode;
}) {
  const [accessToken, setAccessToken] = useState<string | null>(
    null,
  );
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const clearAuth = useCallback(() => {
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");

    setAccessToken(null);
    setUser(null);
  }, []);

  const setTokens = useCallback(
    (access: string, refresh: string) => {
      localStorage.setItem("access_token", access);
      localStorage.setItem("refresh_token", refresh);

      setAccessToken(access);
    },
    [],
  );

  useEffect(() => {
    async function restoreSession() {
      const access = localStorage.getItem("access_token");
      const refresh = localStorage.getItem("refresh_token");

      if (!access || !refresh) {
        setIsLoading(false);
        return;
      }

      try {
        const currentUser = await getCurrentUser(access);

        setAccessToken(access);
        setUser(currentUser);
      } catch {
        try {
          const tokens = await refreshToken(refresh);

          localStorage.setItem(
            "access_token",
            tokens.access,
          );

          localStorage.setItem(
            "refresh_token",
            tokens.refresh,
          );

          const currentUser = await getCurrentUser(
            tokens.access,
          );

          setAccessToken(tokens.access);
          setUser(currentUser);
        } catch {
          clearAuth();
        }
      } finally {
        setIsLoading(false);
      }
    }

    restoreSession();
  }, [clearAuth]);

  const logout = useCallback(async () => {
    const access = localStorage.getItem("access_token");
    const refresh = localStorage.getItem("refresh_token");

    try {
      if (access && refresh) {
        await logoutApi(access, refresh);
      }
    } finally {
      clearAuth();
    }
  }, [clearAuth]);

  return (
    <AuthContext.Provider
      value={{
        accessToken,
        user,
        isAuthenticated: Boolean(accessToken && user),
        isLoading,
        setTokens,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);

  if (!context) {
    throw new Error(
      "useAuth must be used inside AuthProvider",
    );
  }

  return context;
}