import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react';
import { Platform } from 'react-native';
import * as Linking from 'expo-linking';
import * as WebBrowser from 'expo-web-browser';

import { apiFetch } from '@/src/api/client';
import {
  clearAuthSession,
  loadAuthSession,
  saveAuthSession,
} from '@/src/auth/storage';
import type { AuthSession, AuthUser } from '@/src/auth/types';
import { getEveLoginUrl } from '@/src/config/env';

WebBrowser.maybeCompleteAuthSession();

interface SessionResponse {
  character_id: number;
  character_name: string;
  avatar?: string | null;
  user_id?: number | null;
  username?: string | null;
  is_superuser: boolean;
}

function sessionToUser(session: SessionResponse): AuthUser {
  return {
    userId: session.user_id ?? undefined,
    username: session.username ?? undefined,
    characterId: session.character_id,
    characterName: session.character_name,
    avatar: session.avatar ?? undefined,
    isSuperuser: session.is_superuser,
  };
}

interface AuthContextValue {
  user: AuthUser | null;
  token: string | null;
  isLoading: boolean;
  isAuthenticating: boolean;
  loginWithEve: () => Promise<void>;
  loginWithToken: (token: string) => Promise<void>;
  logout: () => Promise<void>;
  refreshProfile: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

function authRedirectUrl(): string {
  return Linking.createURL('auth/callback');
}

function formatLoginError(code: string): string {
  switch (code) {
    case 'DENIED':
      return 'EVE login was cancelled or denied.';
    case 'NOT_CONFIGURED':
      return 'EVE SSO is not configured on the API server.';
    case 'LOGIN_FAILED':
      return 'Could not complete EVE login.';
    default:
      return code;
  }
}

function parseAuthCallbackUrl(url: string): { token?: string; error?: string } {
  const parsed = Linking.parse(url);
  const token = typeof parsed.queryParams?.token === 'string' ? parsed.queryParams.token : undefined;
  const error = typeof parsed.queryParams?.error === 'string' ? parsed.queryParams.error : undefined;
  return { token, error };
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<AuthSession | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isAuthenticating, setIsAuthenticating] = useState(false);

  const applySession = useCallback(async (next: AuthSession | null) => {
    if (next) {
      await saveAuthSession(next);
    } else {
      await clearAuthSession();
    }
    setSession(next);
  }, []);

  const refreshProfile = useCallback(async () => {
    if (!session?.token) {
      return;
    }

    const profile = await apiFetch<SessionResponse>('/api/users/session', {
      token: session.token,
    });
    const nextSession: AuthSession = {
      token: session.token,
      user: sessionToUser(profile),
    };
    await applySession(nextSession);
  }, [applySession, session]);

  const completeLoginFromUrl = useCallback(
    async (url: string) => {
      const { token, error } = parseAuthCallbackUrl(url);
      if (error) {
        throw new Error(formatLoginError(error));
      }
      if (!token) {
        throw new Error('Missing token');
      }

      const profile = await apiFetch<SessionResponse>('/api/users/session', { token });
      const nextSession: AuthSession = {
        token,
        user: sessionToUser(profile),
      };
      await applySession(nextSession);
    },
    [applySession],
  );

  const loginWithToken = useCallback(
    async (token: string) => {
      const profile = await apiFetch<SessionResponse>('/api/users/session', { token });
      const nextSession: AuthSession = {
        token,
        user: sessionToUser(profile),
      };
      await applySession(nextSession);
    },
    [applySession],
  );

  const loginWithEve = useCallback(async () => {
    setIsAuthenticating(true);
    try {
      const redirectUrl = authRedirectUrl();
      const loginUrl = getEveLoginUrl(redirectUrl);

      if (Platform.OS === 'web') {
        window.location.assign(loginUrl);
        return;
      }

      const result = await WebBrowser.openAuthSessionAsync(loginUrl, redirectUrl);

      if (result.type === 'success') {
        await completeLoginFromUrl(result.url);
        return;
      }

      if (result.type === 'cancel' || result.type === 'dismiss') {
        return;
      }

      throw new Error('Login failed');
    } finally {
      setIsAuthenticating(false);
    }
  }, [completeLoginFromUrl]);

  const logout = useCallback(async () => {
    await applySession(null);
  }, [applySession]);

  useEffect(() => {
    let active = true;

    (async () => {
      const stored = await loadAuthSession();
      if (!active) {
        return;
      }
      setSession(stored);
      setIsLoading(false);
    })();

    return () => {
      active = false;
    };
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      user: session?.user ?? null,
      token: session?.token ?? null,
      isLoading,
      isAuthenticating,
      loginWithEve,
      loginWithToken,
      logout,
      refreshProfile,
    }),
    [session, isLoading, isAuthenticating, loginWithEve, loginWithToken, logout, refreshProfile],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return context;
}
