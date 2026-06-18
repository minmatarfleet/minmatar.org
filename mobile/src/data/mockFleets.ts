import type { FleetItem } from '@/src/types/fleets';

export const mockFleets: FleetItem[] = [
  {
    id: 2113,
    type: 'non_strategic',
    audience: 'Warzone',
    description:
      "Arty Thrasher FL33T Roam around the warzone. LEARN Dudes are welcome to come in T1 Thrashers. TFI are SRP'd 20M per hull.",
    objective: 'Thrasher Thursdays!!!',
    doctrine_id: 41,
    start_time: new Date('2026-06-18T20:00:00Z'),
    fleet_commander_id: 2117059479,
    fleet_commander_name: 'MiniSpartan',
    fleet_commander_fleet_count: 8,
    corporation_id: 98726134,
    corporation_name: 'Rattini Tribe',
    location: 'Amamake - 5 times nearly AT winners',
    members_count: 0,
    status: 'pending',
  },
  {
    id: 2123,
    type: 'strategic',
    audience: 'Etherium Reach',
    description:
      "Forming up to defend the R-6KYM Fortizar in Etherium Reach. Expecting some decent numbers from baddies so we'll need a decent showing- make sure you have your jump clones set up.",
    objective: 'Fortizar defense in Etherium Reach',
    doctrine_id: 0,
    start_time: new Date('2026-06-19T02:45:00Z'),
    fleet_commander_id: 634915984,
    fleet_commander_name: 'BearThatCares',
    fleet_commander_fleet_count: 446,
    corporation_id: 98726134,
    corporation_name: 'Rattini Tribe',
    location: 'R-6KYM - Casper Anchored It',
    members_count: 0,
    status: 'pending',
  },
  {
    id: 2116,
    type: 'training',
    audience: 'Warzone',
    description: `FC 101 Class
For aspiring Fleet Commanders and experienced FCs looking to refine their skills.

Topics include:
- FC fundamentals and responsibilities
- Fleet preparation and organization
- Communication and command presence
- Target calling and decision-making
- Common mistakes and lessons learned

Whether you're leading your first fleet or looking to improve your effectiveness, there's something here for you.`,
    objective: 'FC 101 CLASS',
    doctrine_id: 0,
    start_time: new Date('2026-06-19T00:00:00Z'),
    fleet_commander_id: 537400441,
    fleet_commander_name: 'Sevaru',
    fleet_commander_fleet_count: 39,
    corporation_id: 98726134,
    corporation_name: 'Rattini Tribe',
    location: 'Amamake - 5 times nearly AT winners',
    members_count: 0,
    status: 'pending',
  },
  {
    id: 2107,
    type: 'non_strategic',
    audience: 'Warzone',
    description: 'Destroyers',
    objective: 'Chaos',
    doctrine_id: 0,
    start_time: new Date('2026-06-20T01:00:00Z'),
    fleet_commander_id: 93672441,
    fleet_commander_name: 'Orion Sa-Solo',
    fleet_commander_fleet_count: 52,
    corporation_id: 98741376,
    corporation_name: 'Minmatar Fleet Academy',
    location: 'Amamake - 5 times nearly AT winners',
    members_count: 0,
    status: 'pending',
  },
  {
    id: 2120,
    type: 'non_strategic',
    audience: 'Warzone',
    description: `I wanna check out the new people dessie sites and kill stuff along the way. New Bro/L3arn welcome, I will try to focus on teaching as time and context allows.
Main ship will be Arty Thrasher but you can also come as you are. Tackle also very nice or even T3 Destroyers as the new site allows them`,
    objective: 'Thrasher roam and checking out the new 10 people sites',
    doctrine_id: 41,
    start_time: new Date('2026-06-17T19:00:00Z'),
    fleet_commander_id: 2123699290,
    fleet_commander_name: 'Lilith Himmelsgaenger',
    fleet_commander_fleet_count: 3,
    corporation_id: 98741376,
    corporation_name: 'Minmatar Fleet Academy',
    location: 'Amamake - 5 times nearly AT winners',
    members_count: 27,
    status: 'complete',
    tracking: {
      id: 1196312284530,
      start_time: new Date('2026-06-17T19:00:40.850673Z'),
      end_time: new Date('2026-06-17T23:11:26.921824Z'),
      is_registered: true,
    },
  },
  {
    id: 2115,
    type: 'training',
    audience: 'Warzone',
    description: `DREAD 102 Class
For pilots new to dreadnoughts and veterans looking to sharpen their knowledge.

Topics include:
- Dread basics and mechanics
- Advanced tips and tricks
- Choosing the right dread for the job
- Skills, implants, and boosters
- Common mistakes and best practices
- IF YOU NEVER JUMPED - I will be lighting a cyno

Whether you're training into your first dread or have hundreds of siege cycles under your belt, there's something here for you.`,
    objective: 'DREAD 102 Class',
    doctrine_id: 0,
    start_time: new Date('2026-06-18T00:00:00Z'),
    fleet_commander_id: 537400441,
    fleet_commander_name: 'Sevaru',
    fleet_commander_fleet_count: 39,
    corporation_id: 98726134,
    corporation_name: 'Rattini Tribe',
    location: 'Amamake - 5 times nearly AT winners',
    members_count: 1,
    status: 'complete',
    tracking: {
      id: 1289812284514,
      start_time: new Date('2026-06-17T23:53:37.748686Z'),
      end_time: new Date('2026-06-18T00:46:32.050654Z'),
      is_registered: false,
    },
  },
];

function isActiveFleet(fleet: FleetItem): boolean {
  return fleet.status !== 'cancelled' && !!fleet.tracking && !fleet.tracking.end_time;
}

export function getSortedFleets(): FleetItem[] {
  const active = mockFleets.filter(isActiveFleet);
  const pending = mockFleets
    .filter((f) => !isActiveFleet(f) && f.status === 'pending')
    .sort((a, b) => a.start_time.getTime() - b.start_time.getTime());
  const history = mockFleets
    .filter((f) => !isActiveFleet(f) && f.status !== 'pending')
    .sort((a, b) => b.start_time.getTime() - a.start_time.getTime());
  return [...active, ...pending, ...history];
}

export function getFleetById(fleetId: number): FleetItem | undefined {
  return mockFleets.find((f) => f.id === fleetId);
}
