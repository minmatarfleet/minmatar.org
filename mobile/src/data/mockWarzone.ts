import type { WarzoneBriefing, WarzoneSystemHot } from '@/src/types/warzone';

/** Mock Amarr–Minmatar FW systems until backend heatmap exists. */
export const mockWarzoneHotSystems: WarzoneSystemHot[] = [
  {
    system_id: 30002538,
    system_name: 'Vard',
    sun_type_id: 3801,
    contested_percent: 87,
    delta_24h: 12,
    kills_24h: 312,
    front: 'amarr',
    occupier: 'contested',
  },
  {
    system_id: 30002540,
    system_name: 'Lantorn',
    sun_type_id: 3797,
    contested_percent: 72,
    delta_24h: 9,
    kills_24h: 198,
    front: 'amarr',
    occupier: 'minmatar',
  },
  {
    system_id: 30002755,
    system_name: 'Kourmonen',
    sun_type_id: 45032,
    contested_percent: 91,
    delta_24h: 15,
    kills_24h: 524,
    front: 'minmatar',
    occupier: 'contested',
  },
  {
    system_id: 30002756,
    system_name: 'Huola',
    sun_type_id: 3800,
    contested_percent: 78,
    delta_24h: -4,
    kills_24h: 847,
    front: 'minmatar',
    occupier: 'amarr',
  },
  {
    system_id: 30002758,
    system_name: 'Ezzara',
    sun_type_id: 45035,
    contested_percent: 65,
    delta_24h: 8,
    kills_24h: 276,
    front: 'minmatar',
    occupier: 'contested',
  },
  {
    system_id: 30002759,
    system_name: 'Siseide',
    sun_type_id: 3802,
    contested_percent: 84,
    delta_24h: 3,
    kills_24h: 421,
    front: 'amarr',
    occupier: 'amarr',
  },
  {
    system_id: 30002760,
    system_name: 'Otelen',
    sun_type_id: 3798,
    contested_percent: 76,
    delta_24h: 6,
    kills_24h: 355,
    front: 'minmatar',
    occupier: 'minmatar',
  },
  {
    system_id: 30002761,
    system_name: 'Kamola',
    sun_type_id: 45031,
    contested_percent: 68,
    delta_24h: 11,
    kills_24h: 612,
    front: 'amarr',
    occupier: 'contested',
  },
  {
    system_id: 30002762,
    system_name: 'Brin',
    sun_type_id: 6,
    contested_percent: 55,
    delta_24h: 2,
    kills_24h: 143,
    front: 'amarr',
    occupier: 'amarr',
  },
  {
    system_id: 30002763,
    system_name: 'Todifrauan',
    sun_type_id: 45033,
    contested_percent: 62,
    delta_24h: 5,
    kills_24h: 189,
    front: 'minmatar',
    occupier: 'minmatar',
  },
];

function topContestedByFront(front: WarzoneSystemHot['front'], limit: number): WarzoneSystemHot[] {
  return [...mockWarzoneHotSystems]
    .filter((s) => s.front === front)
    .sort((a, b) => b.contested_percent - a.contested_percent)
    .slice(0, limit);
}

export function getWarzoneBriefing(): WarzoneBriefing {
  const hotKills =
    [...mockWarzoneHotSystems].sort((a, b) => b.kills_24h - a.kills_24h)[0] ?? null;

  return {
    amarrContested: topContestedByFront('amarr', 2),
    minmatarContested: topContestedByFront('minmatar', 2),
    hotKills,
  };
}

/** @deprecated Use getWarzoneBriefing — kept for hook swap when backend lands. */
export function getTopHotWarzoneSystems(limit = 5): WarzoneSystemHot[] {
  const { amarrContested, minmatarContested, hotKills } = getWarzoneBriefing();
  const seen = new Set<number>();
  const merged: WarzoneSystemHot[] = [];
  for (const system of [hotKills, ...amarrContested, ...minmatarContested]) {
    if (!system || seen.has(system.system_id)) continue;
    seen.add(system.system_id);
    merged.push(system);
    if (merged.length >= limit) break;
  }
  return merged;
}
