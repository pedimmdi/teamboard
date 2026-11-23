"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
} from "react";

import {
  ApiError,
  getCurrentUser,
  logout as logoutApi,
  type CurrentUser,
  refreshToken,
} from "@/lib/api";

let restoration: Promise<{tokens: Awaited<ReturnType<typeof refreshToken>>; currentUser: CurrentUser}> | null = null;
function restoreAuthSession() {
  if (!restoration) {
    const request = refreshToken().then(async tokens => ({tokens,currentUser:await getCurrentUser(tokens.access)}));
    restoration=request;
    void request.finally(()=>{if(restoration===request)restoration=null;}).catch(()=>{});
  }
  return restoration;
}

type AuthContextValue = {
  accessToken: string | null;
  user: CurrentUser | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  sessionUnavailable: boolean;
  retrySession: () => void;
  setTokens: (
    access: string,
    user: CurrentUser,
  ) => void;
  updateUser: (user: CurrentUser) => void;
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
  const [sessionUnavailable, setSessionUnavailable] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const sessionVersion = useRef(0);

  const clearAuth = useCallback(() => {
    setAccessToken(null);
    setUser(null);
  }, []);

  const setTokens = useCallback(
    (
      access: string,
      currentUser: CurrentUser,
    ) => {
      sessionVersion.current++;
      setAccessToken(access);
      setUser(currentUser);
      setSessionUnavailable(false);
      setIsLoading(false);
    },
    [],
  );

  const updateUser = useCallback((updatedUser: CurrentUser) => {
    setUser(updatedUser);
  }, []);

  const retrySession = useCallback(() => {
    sessionVersion.current++;
    setIsLoading(true);
    setSessionUnavailable(false);
    setAttempt((previous) => previous + 1);
  }, []);

  useEffect(() => {
    const version = sessionVersion.current;
    let cancelled = false;
    const isCurrent = () => !cancelled && version === sessionVersion.current;

    async function restoreSession() {
      try {
        /*
        * The refresh token lives in an HttpOnly cookie.
        * JavaScript cannot read it.
        *
        * We therefore ask the backend for a fresh access token.
        * The browser automatically includes the refresh cookie.
        */
        const {tokens,currentUser} = await restoreAuthSession();

        if (isCurrent()) {
          setAccessToken(tokens.access);
          setUser(currentUser);
        }
      } catch (error) {
        if (isCurrent()) {
          clearAuth();
          setSessionUnavailable(!(error instanceof ApiError && error.status === 401));
        }
      } finally {
        if (isCurrent()) setIsLoading(false);
      }
    }

    function handleTokenRefreshed(
      event: Event,
    ) {
      const customEvent =
        event as CustomEvent<{
          accessToken: string;
        }>;

      const newAccessToken =
        customEvent.detail?.accessToken;

      if (newAccessToken) {
        setAccessToken(newAccessToken);
      }
    }

    function handleAuthLogout() {
      clearAuth();
    }

    window.addEventListener(
      "teamboard:auth-refreshed",
      handleTokenRefreshed,
    );

    window.addEventListener(
      "teamboard:auth-logout",
      handleAuthLogout,
    );

    restoreSession();

    return () => {
      cancelled = true;
      window.removeEventListener(
        "teamboard:auth-refreshed",
        handleTokenRefreshed,
      );

      window.removeEventListener(
        "teamboard:auth-logout",
        handleAuthLogout,
      );
    };
  }, [attempt, clearAuth]);

  const logout = useCallback(async () => {
    sessionVersion.current++;
    if (accessToken) await logoutApi(accessToken);
    clearAuth();
    setIsLoading(false);
    setSessionUnavailable(false);
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
        sessionUnavailable,
        retrySession,
        setTokens,
        updateUser,
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
