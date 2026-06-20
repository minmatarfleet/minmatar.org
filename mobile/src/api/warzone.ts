import { apiFetch } from '@/src/api/client';
import type { ApiWarzoneBriefingResponse } from '@/src/api/types/warzone';

export async function getWarzoneBriefing(): Promise<ApiWarzoneBriefingResponse> {
  return apiFetch<ApiWarzoneBriefingResponse>('/api/feed/warzone');
}
