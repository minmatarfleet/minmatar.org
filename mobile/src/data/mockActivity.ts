import type { ActivityItem } from '@/src/types/activity';

const minutesAgo = (m: number) => new Date(Date.now() - m * 60 * 1000);
const hoursAgo = (h: number) => new Date(Date.now() - h * 60 * 60 * 1000);
const daysAgo = (d: number) => new Date(Date.now() - d * 24 * 60 * 60 * 1000);

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
    roster: [
      { character_id: 634915984, name: 'BearThatCares' },
      { character_id: 2111111111, name: 'Pilot Two' },
      { character_id: 2111111112, name: 'Pilot Three' },
      { character_id: 2111111113, name: 'Pilot Four' },
    ],
    roster_total: 84,
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
    ships: [
      { type_id: 22468, name: 'Rupture', count: 4 },
      { type_id: 16229, name: 'Hurricane', count: 3 },
      { type_id: 12003, name: 'Scythe', count: 2 },
    ],
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
    roster: [
      { character_id: 90000001, name: 'FC Alpha' },
      { character_id: 90000002, name: 'Logi One' },
      { character_id: 90000003, name: 'DPS One' },
    ],
    roster_total: 112,
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
  {
    id: 'kills-yesterday',
    kind: 'killmail_batch',
    timestamp: hoursAgo(26),
    system: 'Auga',
    killmail_count: 19,
    window_minutes: 15,
    summary: 'Evening USTZ push through Auga with steady cruiser trades on both sides.',
  },
  {
    id: 'fleet-yesterday',
    kind: 'fleet_active',
    timestamp: hoursAgo(30),
    faction: 'minmatar',
    system: 'Huola',
    kills: 17,
    pilots: 58,
    composition: 'Hurricane, Scythe, Sabre · shield BC with logi escort',
  },
  {
    id: 'kills-week',
    kind: 'killmail_batch',
    timestamp: daysAgo(3),
    system: 'Kourmonen',
    killmail_count: 34,
    window_minutes: 20,
    summary: 'Weekend flashform chain across Kourmonen and adjacent systems.',
  },
  {
    id: 'militia-week',
    kind: 'militia_joins',
    timestamp: daysAgo(5),
    join_count: 27,
    summary: 'Mid-week enlistment bump ahead of the Huola timer.',
  },
];

export function getActivityFeed(): ActivityItem[] {
  return [...mockActivityFeed].sort((a, b) => b.timestamp.getTime() - a.timestamp.getTime());
}
