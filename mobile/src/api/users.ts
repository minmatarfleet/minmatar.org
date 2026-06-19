import { apiFetch } from '@/src/api/client';
import type { ApiUserProfile } from '@/src/api/types';

export async function getUserProfiles(userIds: number[]): Promise<ApiUserProfile[]> {
  if (userIds.length === 0) {
    return [];
  }
  const ids = [...new Set(userIds)].join(',');
  return apiFetch<ApiUserProfile[]>(`/api/users/profiles?ids=${ids}`);
}

export function profilesByUserId(profiles: ApiUserProfile[]): Map<number, ApiUserProfile> {
  return new Map(profiles.map((p) => [p.user_id, p]));
}
