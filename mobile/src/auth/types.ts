export interface AuthUser {
  userId?: number;
  username?: string;
  characterId: number;
  characterName: string;
  avatar?: string;
  isSuperuser?: boolean;
}

export interface AuthSession {
  token: string;
  user: AuthUser;
}
