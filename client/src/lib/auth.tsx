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
  setTokens: (
    access: string,
    user: CurrentUser,
  ) => void;
  logout: () => Promise<void>;
};

const AuthContext = createContext<
  AuthContextValue | undefined
>(undefined);

export function AuthProvider({
  children,
}: {
  children: React.ReactNode;
}) {
  const [accessToken, setAccessToken] =
    useState<string | null>(null);

  const [user, setUser] =
    useState<CurrentUser | null>(null);

  const [isLoading, setIsLoading] =
    useState(true);

  const clearAuth = useCallback(() => {
    setAccessToken(null);
    setUser(null);
  }, []);

  const setTokens = useCallback(
    (
      access: string,
      currentUser: CurrentUser,
    ) => {
      setAccessToken(access);
      setUser(currentUser);
    },
    [],
  );

  useEffect(() => {
    async function restoreSession() {
      try {
        /*
         * The refresh token lives in an HttpOnly cookie.
         * JavaScript cannot read it.
         *
         * We therefore ask the backend for a fresh access token.
         * The browser automatically includes the refresh cookie.
         */
        const tokens = await refreshToken();

        const currentUser = await getCurrentUser(
          tokens.access,
        );

        setAccessToken(tokens.access);
        setUser(currentUser);
      } catch {
        clearAuth();
      } finally {
        setIsLoading(false);
      }
    }

    restoreSession();
  }, [clearAuth]);

  const logout = useCallback(async () => {
    try {
      if (accessToken) {
        await logoutApi(accessToken);
      }
    } finally {
      clearAuth();
    }
  }, [accessToken, clearAuth]);

  return (
    <AuthContext.Provider
      value={{
        accessToken,
        user,
        isAuthenticated: Boolean(
          accessToken && user,
        ),
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