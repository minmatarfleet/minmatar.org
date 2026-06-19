import { apiFetch } from '@/src/api/client';
import type { ApiFleet, FleetFilter } from '@/src/api/types';

export async function listFleets(token: string, filter: FleetFilter): Promise<ApiFleet[]> {
  return apiFetch<ApiFleet[]>(`/api/fleets/v3?fleet_filter=${filter}`, { token });
}

export async function getFleet(token: string, fleetId: number): Promise<ApiFleet> {
  return apiFetch<ApiFleet>(`/api/fleets/${fleetId}`, { token });
}
