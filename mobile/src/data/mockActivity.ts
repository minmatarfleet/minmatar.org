import type { ActivityItem } from '@/src/types/activity';

const minutesAgo = (m: number) => new Date(Date.now() - m * 60 * 1000);

/** Mock warzone activity until live feeds exist. */
export const mockActivityFeed: ActivityItem[] = [
  {
    id: 'fleet-amarr-1',
    kind: 'fleet_active',
    timestamp: minutesAgo(8),
    faction: 'amarr',
    system: 'Huola',
    kills: 23,
    pilots: 84,
    composition: 'Abaddon, Armageddon, Guardian · armor BS with Scorpion EWAR support',
  },
  {
    id: 'comm-1',
    kind: 'communication',
    timestamp: minutesAgo(14),
    author: 'BearThatCares',
    title: 'Fleet comm',
    message:
      'Urgent: reform Huola gate. Hostiles dropping dreads — need logi and dreads on comms now. Bring cap chains and keep subcaps on grid until cyno is cleared.',
  },
  {
    id: 'kills-1',
    kind: 'killmail_batch',
    timestamp: minutesAgo(18),
    system: 'Huola',
    killmail_count: 47,
    window_minutes: 15,
    summary: 'Heavy fighting at Huola gates. Multiple battleship losses on both sides with logi wing trades.',
  },
  {
    id: 'fleet-minmatar-1',
    kind: 'fleet_active',
    timestamp: minutesAgo(22),
    faction: 'minmatar',
    system: 'Kourmonen',
    kills: 31,
    pilots: 112,
    composition: 'Hurricane, Ferox, Scythe · shield BC with Scimitar logi wing',
  },
  {
    id: 'militia-1',
    kind: 'militia_joins',
    timestamp: minutesAgo(35),
    join_count: 18,
    summary: 'Fresh enlistments from Metropolis trade hubs. Most flagged for PVP cert tracking.',
  },
  {
    id: 'fleet-pirate-1',
    kind: 'fleet_active',
    timestamp: minutesAgo(41),
    faction: 'pirate',
    system: 'Tama',
    kills: 9,
    pilots: 26,
    composition: 'Cyno, Rattlesnake, Loki · blops hunting pipeline traffic',
  },
  {
    id: 'kills-2',
    kind: 'killmail_batch',
    timestamp: minutesAgo(52),
    system: 'Siseide',
    killmail_count: 28,
    window_minutes: 20,
    summary: 'Skirmish chain through Siseide and adjacent low-sec. Cruiser and T3 losses dominate the feed.',
  },
  {
    id: 'comm-2',
    kind: 'communication',
    timestamp: minutesAgo(68),
    author: 'Uchoda Risalo',
    title: 'Direct announcement',
    message:
      'All Minmatar fleets: push Ezzara i-hub after tonight\'s form. Kitchen sink, militia comms. FCs ping when ready to move from staging.',
  },
  {
    id: 'fleet-minmatar-2',
    kind: 'fleet_active',
    timestamp: minutesAgo(75),
    faction: 'minmatar',
    system: 'Ezzara',
    kills: 14,
    pilots: 67,
    composition: 'Cyclone, Scimitar, Sabre · fast shield with interceptor tackle',
  },
  {
    id: 'militia-2',
    kind: 'militia_joins',
    timestamp: minutesAgo(120),
    join_count: 42,
    summary: 'Largest enlistment spike this week. Recruits routed to Huola and Kourmonen orientation fleets.',
  },
  {
    id: 'fleet-amarr-2',
    kind: 'fleet_active',
    timestamp: minutesAgo(145),
    faction: 'amarr',
    system: 'Vard',
    kills: 6,
    pilots: 38,
    composition: 'Oracle, Heretic, Magus · arty alpha strike with HFI support',
  },
  {
    id: 'comm-3',
    kind: 'communication',
    timestamp: minutesAgo(180),
    author: 'FC Desk',
    title: 'Ops update',
    message:
      'Amarr fleet stood down in Lantorn. Minmatar still active on front — watch Kourmonen cyno. Next ping expected at form time.',
  },
];

export function getActivityFeed(): ActivityItem[] {
  return [...mockActivityFeed].sort((a, b) => b.timestamp.getTime() - a.timestamp.getTime());
}
