import { apiFetch } from '@/src/api/client';
import type { ApiFeedListResponse } from '@/src/api/types/feed';

export interface ListFeedParams {
  cursor?: string;
  limit?: number;
  days?: number;
}

export async function listFeed(params: ListFeedParams = {}): Promise<ApiFeedListResponse> {
  const query = new URLSearchParams();
  if (params.cursor) query.set('cursor', params.cursor);
  if (params.limit != null) query.set('limit', String(params.limit));
  if (params.days != null) query.set('days', String(params.days));
  const qs = query.toString();
  const path = qs ? `/api/feed/?${qs}` : '/api/feed/';
  return apiFetch<ApiFeedListResponse>(path);
}
