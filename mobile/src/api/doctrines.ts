import { apiFetch } from '@/src/api/client';
import type { ApiDoctrine } from '@/src/api/types';

export async function getDoctrine(doctrineId: number): Promise<ApiDoctrine> {
  return apiFetch<ApiDoctrine>(`/api/doctrines/${doctrineId}`);
}
