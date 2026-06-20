import { useCallback, useEffect, useState } from 'react';

import { listFleets } from '@/src/api/fleets';
import { isActiveFleet, isUpcomingFleet, mapApiFleetToItem } from '@/src/api/mappers/fleets';
import { getUserProfiles, profilesByUserId } from '@/src/api/users';
import type { FleetFilter } from '@/src/api/types';
import type { FleetItem } from '@/src/types/fleets';

async function enrichFleets(token: string, filter: FleetFilter): Promise<FleetItem[]> {
  const raw = await listFleets(token, filter);
  const withCommander = raw.filter((f) => f.fleet_commander);
  const profiles = await getUserProfiles(withCommander.map((f) => f.fleet_commander));
  const profileMap = profilesByUserId(profiles);

  return withCommander.map((fleet) => {
    const profile = profileMap.get(fleet.fleet_commander);
    const name =
      profile?.eve_character_profile?.character_name ?? profile?.username ?? 'Unknown FC';
    const characterId = profile?.eve_character_profile?.character_id ?? 0;
    return mapApiFleetToItem(fleet, name, characterId);
  });
}

export function useFleetsSchedule(token: string | null) {
  const [fleets, setFleets] = useState<FleetItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!token) {
      setFleets([]);
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const [active, upcoming, recent] = await Promise.all([
        enrichFleets(token, 'active'),
        enrichFleets(token, 'upcoming'),
        enrichFleets(token, 'recent'),
      ]);
      const byId = new Map<number, FleetItem>();
      [...recent, ...upcoming, ...active].forEach((f) => byId.set(f.id, f));
      setFleets([...byId.values()].sort((a, b) => a.start_time.getTime() - b.start_time.getTime()));
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load fleets');
      setFleets([]);
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    void load();
  }, [load]);

  const active = fleets.filter(isActiveFleet);
  const upcoming = fleets.filter(isUpcomingFleet);
  const recent = fleets.filter((f) => !isActiveFleet(f) && !isUpcomingFleet(f));

  return { fleets, active, upcoming, recent, loading, error, reload: load };
}

export async function fetchFleetById(token: string, fleetId: number): Promise<FleetItem | null> {
  const { getFleet } = await import('@/src/api/fleets');
  try {
    const raw = await getFleet(token, fleetId);
    const profiles = await getUserProfiles([raw.fleet_commander]);
    const profile = profiles[0];
    const name =
      profile?.eve_character_profile?.character_name ?? profile?.username ?? 'Unknown FC';
    const characterId = profile?.eve_character_profile?.character_id ?? 0;
    return mapApiFleetToItem(raw, name, characterId);
  } catch {
    return null;
  }
}

export async function fetchRecentAarFleet(token: string): Promise<FleetItem | null> {
  const recent = await enrichFleets(token, 'recent');
  return recent.find((f) => f.aar_link) ?? null;
}

export { enrichFleets, isActiveFleet, isUpcomingFleet };
