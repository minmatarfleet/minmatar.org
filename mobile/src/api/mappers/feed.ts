import type { ApiFeedEventItem } from '@/src/api/types/feed';
import type { ActivityItem, ActivityKind, ActivityPilot, ActivityShip } from '@/src/types/activity';

const KIND_MAP: Record<string, ActivityKind> = {
  fleet_active: 'fleet_active',
  killmail_batch: 'killmail_batch',
  communication: 'communication',
  militia_joins: 'militia_joins',
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
        system: (payload.system_name as string) ?? undefined,
        kills: payload.kills as number | undefined,
        pilots: payload.pilots as number | undefined,
        composition: item.body || item.preview || undefined,
        roster: mapRoster(payload),
        roster_total: payload.roster_total as number | undefined,
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
    case 'communication':
      return {
        ...base,
        author: (payload.author as string) ?? item.subheader,
        title: item.title,
        message: item.body || item.preview,
      };
    case 'militia_joins':
      return {
        ...base,
        join_count: payload.join_count as number | undefined,
        summary: item.preview || item.body || undefined,
      };
    default:
      return base;
  }
}

export function mapApiFeedToActivity(items: ApiFeedEventItem[] | null | undefined): ActivityItem[] {
  return (items ?? []).map(mapApiFeedItemToActivity);
}
