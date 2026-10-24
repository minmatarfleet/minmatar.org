import type { ApiFeedEventItem } from '@/src/api/types/feed';
import type { ActivityItem, ActivityKind, ActivityPilot, ActivityShip } from '@/src/types/activity';

const KIND_MAP: Record<string, ActivityKind> = {
  fleet_active: 'fleet_active',
  killmail_batch: 'killmail_batch',
  communication: 'communication',
  contested_change: 'contested_change',
  fleet_kills: 'fleet_kills',
};

function mapRoster(payload: Record<string, unknown>): ActivityPilot[] | undefined {
  const roster = payload.roster;
  if (!Array.isArray(roster) || roster.length === 0) return undefined;
  return roster
    .map((entry) => {
      if (!entry || typeof entry !== 'object') return null;
      const row = entry as Record<string, unknown>;
      const character_id = row.character_id;
      const name = row.name;
      if (typeof character_id !== 'number' || typeof name !== 'string') return null;
      return { character_id, name };
    })
    .filter((entry): entry is ActivityPilot => entry != null);
}

function mapShips(payload: Record<string, unknown>): ActivityShip[] | undefined {
  const ships = payload.ships;
  if (!Array.isArray(ships) || ships.length === 0) return undefined;
  return ships
    .map((entry) => {
      if (!entry || typeof entry !== 'object') return null;
      const row = entry as Record<string, unknown>;
      const name = row.name;
      const count = row.count;
      const type_id = row.type_id;
      if (typeof name !== 'string' || typeof count !== 'number') return null;
      return {
        name,
        count,
        ...(typeof type_id === 'number' ? { type_id } : {}),
      };
    })
    .filter((entry): entry is ActivityShip => entry != null);
}

function mapHeadlineShips(payload: Record<string, unknown>): ActivityShip[] | undefined {
  const headline = payload.headline;
  const killmails = payload.killmails;
  if (!Array.isArray(headline) || !Array.isArray(killmails)) return undefined;
  const byId = new Map<unknown, Record<string, unknown>>();
  for (const entry of killmails) {
    if (entry && typeof entry === 'object') {
      const row = entry as Record<string, unknown>;
      byId.set(row.killmail_id, row);
    }
  }
  const ships = headline
    .map((killmailId) => byId.get(killmailId))
    .filter((row): row is Record<string, unknown> => row != null)
    .map((row) => ({
      name: typeof row.victim_ship_name === 'string' ? row.victim_ship_name : 'Unknown',
      count: 1,
      ...(typeof row.victim_ship_type_id === 'number' ? { type_id: row.victim_ship_type_id } : {}),
    }));
  return ships.length ? ships : undefined;
}

function mapSystemNames(payload: Record<string, unknown>): string[] | undefined {
  const systems = payload.systems;
  if (!Array.isArray(systems)) return undefined;
  const names = systems
    .map((entry) =>
      entry && typeof entry === 'object' ? (entry as Record<string, unknown>).system_name : null,
    )
    .filter((name): name is string => typeof name === 'string');
  return names.length ? names : undefined;
}

export function mapApiFeedItemToActivity(item: ApiFeedEventItem): ActivityItem {
  const kind = KIND_MAP[item.kind] ?? 'communication';
  const payload = item.payload ?? {};
  const base: ActivityItem = {
    id: item.id,
    kind,
    timestamp: new Date(item.occurred_at),
    title: item.title,
    subheader: item.subheader,
    summary: item.preview || item.body || undefined,
  };

  switch (kind) {
    case 'fleet_active':
      return {
        ...base,
        faction: (payload.faction as ActivityItem['faction']) ?? undefined,
        formation:
          payload.formation === 'gang' || payload.formation === 'fleet'
            ? payload.formation
            : undefined,
        system: (payload.system_name as string) ?? undefined,
        kills: payload.kills as number | undefined,
        pilots: payload.pilots as number | undefined,
        composition: item.body || item.preview || undefined,
        roster: mapRoster(payload),
        roster_total: payload.roster_total as number | undefined,
        engagement_tier: payload.engagement_tier as string | undefined,
        previous_tier: payload.previous_tier as string | undefined,
        upgraded_at: payload.upgraded_at as string | undefined,
      };
    case 'killmail_batch':
      return {
        ...base,
        system: (payload.system_name as string) ?? undefined,
        killmail_count: payload.killmail_count as number | undefined,
        window_minutes: payload.window_minutes as number | undefined,
        kills: payload.kills as number | undefined,
        pilots: payload.pilots as number | undefined,
        ships: mapShips(payload),
        summary: item.preview || item.body || undefined,
      };
    case 'fleet_kills':
      return {
        ...base,
        isk_destroyed: payload.isk_destroyed as number | undefined,
        isk_lost: payload.isk_lost as number | undefined,
        ships_destroyed: payload.ships_destroyed as number | undefined,
        ships_lost: payload.ships_lost as number | undefined,
        systems: mapSystemNames(payload),
        ships: mapHeadlineShips(payload),
      };
    case 'communication':
      return {
        ...base,
        author: (payload.author as string) ?? item.subheader,
        title: item.title,
        message: item.body || item.preview,
      };
    case 'contested_change':
      return {
        ...base,
        system: (payload.system_name as string) ?? undefined,
        contested_percent: payload.contested_percent as number | undefined,
        delta_percent: payload.delta_percent as number | undefined,
        faction: (payload.occupier as ActivityItem['faction']) ?? undefined,
        summary: item.preview || item.body || undefined,
      };
    default:
      return base;
  }
}

export function mapApiFeedToActivity(items: ApiFeedEventItem[] | null | undefined): ActivityItem[] {
  return (items ?? []).map(mapApiFeedItemToActivity);
}
