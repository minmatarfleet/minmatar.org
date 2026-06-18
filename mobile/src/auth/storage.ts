import * as SecureStore from 'expo-secure-store';

import type { AuthSession, AuthUser } from '@/src/auth/types';

const TOKEN_KEY = 'minmatar_auth_token';
const USER_KEY = 'minmatar_auth_user';

export async function loadAuthSession(): Promise<AuthSession | null> {
  const token = await SecureStore.getItemAsync(TOKEN_KEY);
  const userJson = await SecureStore.getItemAsync(USER_KEY);
  if (!token || !userJson) {
    return null;
  }

  try {
    const user = JSON.parse(userJson) as AuthUser;
    return { token, user };
  } catch {
    await clearAuthSession();
    return null;
  }
}

export async function saveAuthSession(session: AuthSession): Promise<void> {
  await SecureStore.setItemAsync(TOKEN_KEY, session.token);
  await SecureStore.setItemAsync(USER_KEY, JSON.stringify(session.user));
}

export async function clearAuthSession(): Promise<void> {
  await SecureStore.deleteItemAsync(TOKEN_KEY);
  await SecureStore.deleteItemAsync(USER_KEY);
}

export function userFromJwtPayload(payload: Record<string, unknown>): AuthUser {
  return {
    userId: payload.user_id ? Number(payload.user_id) : undefined,
    username: payload.username ? String(payload.username) : undefined,
    characterId: Number(payload.character_id),
    characterName: String(payload.character_name ?? ''),
    avatar: payload.avatar ? String(payload.avatar) : undefined,
    isSuperuser: Boolean(payload.is_superuser),
  };
}
