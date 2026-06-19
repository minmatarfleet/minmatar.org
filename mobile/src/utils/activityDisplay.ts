import type { ActivityItem } from '@/src/types/activity';
import { colors } from '@/src/theme/colors';

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
}

const factionLabel = {
  amarr: 'Amarr',
  minmatar: 'Minmatar',
  pirate: 'Pirate',
} as const;

export function mapActivityToCard(item: ActivityItem): ActivityCardContent {
  if (item.title) {
    return {
      title: item.title,
      subheader:
        item.system ??
        item.author ??
        (item.join_count ? `${item.join_count} pilots` : 'Warzone'),
      preview: item.summary ?? item.message ?? item.composition ?? '',
    };
  }

  switch (item.kind) {
    case 'fleet_active':
      return {
        title: `${factionLabel[item.faction ?? 'pirate']} fleet active`,
        subheader: [item.system, item.kills != null ? `${item.kills} kills` : null, item.pilots != null ? `${item.pilots} pilots` : null]
          .filter(Boolean)
          .join(' · '),
        preview: item.composition ?? 'Active on front lines.',
      };
    case 'killmail_batch':
      return {
        title: `${item.killmail_count ?? 0} killmails in ${item.window_minutes ?? 0} min`,
        subheader: item.system ?? 'Warzone',
        preview: item.summary ?? 'Kill burst reported.',
      };
    case 'communication':
      return {
        title: item.title ?? 'Communication',
        subheader: item.author ?? 'Fleet command',
        preview: item.message ?? '',
      };
    case 'militia_joins':
      return {
        title: `${item.join_count ?? 0} pilots newly active in warzone`,
        subheader: 'Minmatar militia',
        preview: item.summary ?? 'New pilots active in warzone killmails.',
      };
  }
}
