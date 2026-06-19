import { Platform } from 'react-native';
import * as SecureStore from 'expo-secure-store';

import type { AuthSession, AuthUser } from '@/src/auth/types';

const TOKEN_KEY = 'minmatar_auth_token';
const USER_KEY = 'minmatar_auth_user';

async function getItem(key: string): Promise<string | null> {
  if (Platform.OS === 'web') {
    return localStorage.getItem(key);
  }
  return SecureStore.getItemAsync(key);
}

async function setItem(key: string, value: string): Promise<void> {
  if (Platform.OS === 'web') {
    localStorage.setItem(key, value);
    return;
  }
  await SecureStore.setItemAsync(key, value);
}

async function deleteItem(key: string): Promise<void> {
  if (Platform.OS === 'web') {
    localStorage.removeItem(key);
    return;
  }
  await SecureStore.deleteItemAsync(key);
}

export async function loadAuthSession(): Promise<AuthSession | null> {
  const token = await getItem(TOKEN_KEY);
  const userJson = await getItem(USER_KEY);
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
  await setItem(TOKEN_KEY, session.token);
  await setItem(USER_KEY, JSON.stringify(session.user));
}

export async function clearAuthSession(): Promise<void> {
  await deleteItem(TOKEN_KEY);
  await deleteItem(USER_KEY);
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
