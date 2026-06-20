import type { ApiFeedEventItem } from '@/src/api/types/feed';
import type { ActivityItem, ActivityKind } from '@/src/types/activity';

const KIND_MAP: Record<string, ActivityKind> = {
  fleet_active: 'fleet_active',
  killmail_batch: 'killmail_batch',
  communication: 'communication',
  militia_joins: 'militia_joins',
};

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
      };
    case 'killmail_batch':
      return {
        ...base,
        system: (payload.system_name as string) ?? undefined,
        killmail_count: payload.killmail_count as number | undefined,
        window_minutes: payload.window_minutes as number | undefined,
        kills: payload.kills as number | undefined,
        pilots: payload.pilots as number | undefined,
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
