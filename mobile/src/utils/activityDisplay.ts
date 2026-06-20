import type { ActivityFaction, ActivityItem, ActivityKind } from '@/src/types/activity';
import { colors } from '@/src/theme/colors';

export const ACTIVITY_CARD_MIN_HEIGHT = 96;
export const ACTIVITY_PREVIEW_MAX_CHARS = 64;
export const ACTIVITY_PREVIEW_LINES = 1;

export type ActivityAccent = 'combat' | 'militia' | 'amarr';

export interface ActivityAccentStyle {
  accent: string;
  nodeBg: string;
}

const accentStyles: Record<ActivityAccent, ActivityAccentStyle> = {
  combat: { accent: colors.fleetRed, nodeBg: colors.fleetRedMuted },
  militia: { accent: colors.militiaPurple, nodeBg: 'rgba(115, 66, 178, 0.18)' },
  amarr: { accent: colors.fleetYellow, nodeBg: 'rgba(241, 217, 160, 0.14)' },
};

/** Combat + FC comms → red; Minmatar militia → purple; Amarr → yellow. */
export function getActivityAccent(item: ActivityItem): ActivityAccentStyle {
  switch (item.kind) {
    case 'killmail_batch':
    case 'communication':
      return accentStyles.combat;
    case 'militia_joins':
      return accentStyles.militia;
    case 'fleet_active':
      if (item.faction === 'amarr') return accentStyles.amarr;
      if (item.faction === 'minmatar') return accentStyles.militia;
      return accentStyles.combat;
  }
}

export interface ActivityCardContent {
  title: string;
  subheader: string;
  preview: string;
  entityLine?: string;
}

export interface ActivityDetailSection {
  label: string;
  value: string;
}

export interface ActivityDetail {
  kind: ActivityKind;
  timestamp: Date;
  title: string;
  subheader: string;
  body?: string;
  sections: ActivityDetailSection[];
}

const factionLabel: Record<ActivityFaction, string> = {
  amarr: 'Amarr',
  minmatar: 'Minmatar',
  pirate: 'Pirate',
};

function formatRosterLine(item: ActivityItem): string | undefined {
  if (!item.roster?.length) return undefined;
  const names = item.roster.map((pilot) => pilot.name).join(' · ');
  if (item.roster_total != null && item.roster_total > item.roster.length) {
    return `${names} +${item.roster_total - item.roster.length}`;
  }
  return names;
}

function formatShipsLine(item: ActivityItem): string | undefined {
  if (!item.ships?.length) return undefined;
  return item.ships
    .map((ship) => (ship.count > 1 ? `${ship.name} ×${ship.count}` : ship.name))
    .join(' · ');
}

function truncate(text: string, max = ACTIVITY_PREVIEW_MAX_CHARS): string {
  const trimmed = text.trim();
  if (trimmed.length <= max) return trimmed;
  return `${trimmed.slice(0, max - 1).trimEnd()}…`;
}

export function kindLabel(kind: ActivityKind): string {
  switch (kind) {
    case 'fleet_active':
      return 'Fleet';
    case 'killmail_batch':
      return 'Combat activity';
    case 'communication':
      return 'Comms';
    case 'militia_joins':
      return 'Militia';
  }
}

function fallbackSubheader(item: ActivityItem): string {
  if (item.subheader) return item.subheader;
  if (item.system) return item.system;
  if (item.author) return item.author;
  if (item.join_count != null) return `${item.join_count} pilots`;
  return 'Warzone';
}

export function mapActivityToCard(item: ActivityItem): ActivityCardContent {
  const entityLine =
    item.kind === 'fleet_active'
      ? formatRosterLine(item)
      : item.kind === 'killmail_batch'
        ? formatShipsLine(item)
        : undefined;

  if (item.title) {
    return {
      title: item.title,
      subheader: fallbackSubheader(item),
      preview: truncate(item.summary ?? item.message ?? item.composition ?? ''),
      entityLine,
    };
  }

  switch (item.kind) {
    case 'fleet_active':
      return {
        title: `${factionLabel[item.faction ?? 'pirate']} fleet active`,
        subheader: [item.system, item.kills != null ? `${item.kills} kills` : null, item.pilots != null ? `${item.pilots} pilots` : null]
          .filter(Boolean)
          .join(' · '),
        preview: truncate(item.composition ?? 'Active on front lines.'),
        entityLine,
      };
    case 'killmail_batch':
      return {
        title: item.title ?? `${item.killmail_count ?? 0} killmails in ${item.window_minutes ?? 0} min`,
        subheader: fallbackSubheader(item),
        preview: truncate(item.summary ?? `Fighting reported in ${item.system ?? 'the warzone'}.`),
        entityLine,
      };
    case 'communication':
      return {
        title: item.title ?? 'Communication',
        subheader: item.author ?? 'Fleet command',
        preview: truncate(item.message ?? 'No message content.'),
      };
    case 'militia_joins':
      return {
        title: `${item.join_count ?? 0} pilots newly active in warzone`,
        subheader: 'Minmatar militia',
        preview: truncate(item.summary ?? 'New pilots active in warzone killmails.'),
      };
  }
}

export function mapActivityToDetail(item: ActivityItem): ActivityDetail {
  const card = mapActivityToCard(item);

  switch (item.kind) {
    case 'fleet_active':
      return {
        kind: item.kind,
        timestamp: item.timestamp,
        title: card.title,
        subheader: card.subheader,
        body: item.composition,
        sections: [
          { label: 'System', value: item.system ?? '—' },
          { label: 'Kills', value: String(item.kills ?? 0) },
          { label: 'Pilots', value: String(item.pilots ?? 0) },
          { label: 'Faction', value: factionLabel[item.faction ?? 'pirate'] },
          ...(formatRosterLine(item)
            ? [{ label: 'Fleet', value: formatRosterLine(item)! }]
            : []),
          { label: 'Composition', value: item.composition ?? '—' },
        ],
      };
    case 'killmail_batch':
      return {
        kind: item.kind,
        timestamp: item.timestamp,
        title: card.title,
        subheader: card.subheader,
        body: item.summary,
        sections: [
          { label: 'System', value: item.system ?? '—' },
          { label: 'Kills', value: String(item.kills ?? item.killmail_count ?? 0) },
          { label: 'Pilots', value: String(item.pilots ?? '—') },
          { label: 'Window', value: `${item.window_minutes ?? 0} min` },
          ...(formatShipsLine(item) ? [{ label: 'Losses', value: formatShipsLine(item)! }] : []),
        ],
      };
    case 'communication':
      return {
        kind: item.kind,
        timestamp: item.timestamp,
        title: card.title,
        subheader: card.subheader,
        body: item.message,
        sections: [
          { label: 'From', value: item.author ?? '—' },
          { label: 'Type', value: item.title ?? 'Communication' },
        ],
      };
    case 'militia_joins':
      return {
        kind: item.kind,
        timestamp: item.timestamp,
        title: card.title,
        subheader: card.subheader,
        body: item.summary ?? 'New pilots active in warzone killmails.',
        sections: [
          { label: 'Pilots', value: String(item.join_count ?? 0) },
          { label: 'Faction', value: 'Minmatar militia' },
        ],
      };
  }
}
