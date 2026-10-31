import type { WarzoneIssue } from './types'
import {
    AMARR_FLEET,
    AMARR_SMALL_GANG,
    AMARR_SOLO,
    BOARDS_SAMPLED_KILLS,
    BOARDS_SAMPLED_KILLS_VS,
    BOARDS_TOTAL_ISK,
    BOARDS_TOTAL_ISK_VS,
    FRONTS,
    GROUPS,
    MINMATAR_FLEET,
    MINMATAR_SMALL_GANG,
    MINMATAR_SOLO,
    SCOREBOARD_STATS,
    SHIPS_FLEET,
    SHIPS_SMALL_GANG,
    SHIPS_SOLO,
    SYSTEM_STATS,
    TRAFFIC,
} from './yc128-10-boards'

export const SLUG = 'yc128-10' as const
export const PERMALINK_PATH = `/warzone/${SLUG}/` as const
export const LATEST_PATH = '/warzone/' as const
export const COVER_IMAGE = '/images/warzone-cover.jpg'

/** Compact count label: 1_118_133 -> "1.12M", 34_527 -> "34.5k". */
function count_label(value: number): string {
    if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(2)}M`
    if (value >= 1_000) return `${(value / 1_000).toFixed(1)}k`
    return String(value)
}

const STAT_BY_NAME = new Map(SYSTEM_STATS.map((row) => [row.system, row]))
type SystemName = (typeof SYSTEM_STATS)[number]['system']
function system_stat(name: SystemName) {
    const row = STAT_BY_NAME.get(name)
    if (!row) throw new Error(`No warzone stats for system ${name}`)
    return row
}

const AMAMAKE_ZKILL = 'https://zkillboard.com/system/30002537/'

export const YC128_10: WarzoneIssue = {
    slug: SLUG,
    permalink_path: PERMALINK_PATH,
    cover_image: COVER_IMAGE,
    published_at: new Date('2026-10-31T00:00:00Z'),
    period_utc: '1–31 Oct 2026 UTC',
    previous_period_label: 'September',
    esi_as_of: '31 Oct 2026',
    who_won: 'Minmatar took one system. Amamake cost 461 billion.',
    opening:
        'October ended 27 systems Minmatar, 43 Amarr, one more than September. Minmatar took Gebuladi, Sirekur, and Frerstorn. Amarr took Helgatild and Evati. On the tenth Amamake threw another birthday brawl, and a Hel died. That night is the focus below.',
    sampled_ships: BOARDS_SAMPLED_KILLS,
    sampled_isk: BOARDS_TOTAL_ISK,
    sampled_ships_vs: BOARDS_SAMPLED_KILLS_VS,
    sampled_isk_vs: BOARDS_TOTAL_ISK_VS,
    focus_name: 'Amamake',
    occupancy_changes: 11,
    occupancy_net_amarr: -1,
    systems_that_moved: 5,
    occupancy_dek:
        'Five systems finished in new hands, and the month ended 27 Minmatar, 43 Amarr. Minmatar took Gebuladi, Sirekur, and Frerstorn. Amarr took Helgatild and Evati. Klogori spent a day with the Angel Cartel and was Minmatar again on the fourth. Huola changed hands four times and finished Amarr.',
    scoreboard: [
        {
            militia: 'minmatar',
            occupancy_net: 1,
            systems_held: SCOREBOARD_STATS.minmatar.systems,
            enlisted_pilots: SCOREBOARD_STATS.minmatar.pilots,
            enlisted_pilots_label: count_label(SCOREBOARD_STATS.minmatar.pilots),
            active_pilots: SCOREBOARD_STATS.minmatar.active_pilots,
            active_pilots_label: SCOREBOARD_STATS.minmatar.active_pilots.toLocaleString('en-US'),
            active_pilots_vs: SCOREBOARD_STATS.minmatar.active_pilots_vs,
            kills: SCOREBOARD_STATS.minmatar.kills,
            kills_vs: SCOREBOARD_STATS.minmatar.kills_vs,
            victory_points_last_week: SCOREBOARD_STATS.minmatar.victory_points_last_week,
            victory_points_last_week_label: count_label(SCOREBOARD_STATS.minmatar.victory_points_last_week),
        },
        {
            militia: 'amarr',
            occupancy_net: -1,
            systems_held: SCOREBOARD_STATS.amarr.systems,
            enlisted_pilots: SCOREBOARD_STATS.amarr.pilots,
            enlisted_pilots_label: count_label(SCOREBOARD_STATS.amarr.pilots),
            active_pilots: SCOREBOARD_STATS.amarr.active_pilots,
            active_pilots_label: SCOREBOARD_STATS.amarr.active_pilots.toLocaleString('en-US'),
            active_pilots_vs: SCOREBOARD_STATS.amarr.active_pilots_vs,
            kills: SCOREBOARD_STATS.amarr.kills,
            kills_vs: SCOREBOARD_STATS.amarr.kills_vs,
            victory_points_last_week: SCOREBOARD_STATS.amarr.victory_points_last_week,
            victory_points_last_week_label: count_label(SCOREBOARD_STATS.amarr.victory_points_last_week),
        },
    ],
    fights: [
        {
            system: 'Amamake',
            date_label: '10 Oct',
            dek: 'The birthday brawl. From 22:00 to midnight, Amamake lost a Hel, a Vehement, and a stack of dreadnoughts.',
            ships: system_stat('Amamake').ships,
            isk_label: system_stat('Amamake').isk_label,
            vs_last_month: system_stat('Amamake').vs_last_month,
            links: [
                { href: AMAMAKE_ZKILL, label: 'zKill' },
            ],
        },
    ],
    occupancy: [
        {
            date_label: '3 Oct',
            system: 'Gebuladi',
            taken_by: 'minmatar',
            ships: system_stat('Gebuladi').ships,
            vs_last_month: system_stat('Gebuladi').vs_last_month,
            isk_label: system_stat('Gebuladi').isk_label,
            holds_today: system_stat('Gebuladi').holds_today,
            dotlan_href: 'https://evemaps.dotlan.net/system/Gebuladi',
            zkill_href: 'https://zkillboard.com/system/30002093/',
        },
        {
            date_label: '5 Oct',
            system: 'Sirekur',
            taken_by: 'minmatar',
            ships: system_stat('Sirekur').ships,
            vs_last_month: system_stat('Sirekur').vs_last_month,
            isk_label: system_stat('Sirekur').isk_label,
            holds_today: system_stat('Sirekur').holds_today,
            dotlan_href: 'https://evemaps.dotlan.net/system/Sirekur',
            zkill_href: 'https://zkillboard.com/system/30002092/',
        },
        {
            date_label: '5 Oct',
            system: 'Helgatild',
            taken_by: 'amarr',
            ships: system_stat('Helgatild').ships,
            vs_last_month: system_stat('Helgatild').vs_last_month,
            isk_label: system_stat('Helgatild').isk_label,
            holds_today: system_stat('Helgatild').holds_today,
            dotlan_href: 'https://evemaps.dotlan.net/system/Helgatild',
            zkill_href: 'https://zkillboard.com/system/30002063/',
        },
        {
            date_label: '8 Oct',
            system: 'Frerstorn',
            taken_by: 'minmatar',
            ships: system_stat('Frerstorn').ships,
            vs_last_month: system_stat('Frerstorn').vs_last_month,
            isk_label: system_stat('Frerstorn').isk_label,
            holds_today: system_stat('Frerstorn').holds_today,
            dotlan_href: 'https://evemaps.dotlan.net/system/Frerstorn',
            zkill_href: 'https://zkillboard.com/system/30002090/',
        },
        {
            date_label: '11 Oct',
            system: 'Evati',
            taken_by: 'amarr',
            ships: system_stat('Evati').ships,
            vs_last_month: system_stat('Evati').vs_last_month,
            isk_label: system_stat('Evati').isk_label,
            holds_today: system_stat('Evati').holds_today,
            dotlan_href: 'https://evemaps.dotlan.net/system/Evati',
            zkill_href: 'https://zkillboard.com/system/30002060/',
        },
    ],
    traffic: TRAFFIC,
    traffic_footnote:
        'Busiest systems by ships destroyed in October, across all 70 warzone systems. Source: zKillboard per-system API, capsules removed.',
    fronts: [
        {
            name: 'Minmatar front',
            regions: 'Heimatar and Metropolis',
            occupancy_label: '7 occupancy changes',
            ships: FRONTS.minmatar.ships,
            ships_label: FRONTS.minmatar.ships_label,
            ships_vs: FRONTS.minmatar.ships_vs,
            hottest_system: FRONTS.minmatar.hottest_system,
            dek: 'Heimatar and Metropolis. Still where most of the war is fought. Amamake led the warzone again, and the tenth is why. Seven systems changed hands here. Minmatar took Gebuladi, Sirekur, and Frerstorn. Amarr took Helgatild and Evati. Klogori flipped to the Angel Cartel and back.',
        },
        {
            name: 'Amarr front',
            regions: 'Devoid and The Bleak Lands',
            occupancy_label: '4 occupancy changes',
            ships: FRONTS.amarr.ships,
            ships_label: FRONTS.amarr.ships_label,
            ships_vs: FRONTS.amarr.ships_vs,
            hottest_system: FRONTS.amarr.hottest_system,
            dek: 'Devoid and The Bleak Lands. Kourmonen was the loudest system here, quieter than September. Huola was the map story: Angel Cartel on the twenty-second, Minmatar on the twenty-third, Amarr again on the twenty-sixth.',
        },
    ],
    focus: {
        title: 'Amamake: 461B down',
        window_label: '10 Oct · 22:00–00:00',
        section_dek:
            'One story that would not fit a normal issue: two hours in Amamake on the tenth, when a birthday brawl turned into a 461-billion-ISK capital fight.',
        cta_label: 'Amamake on zKillboard',
        dek: [
            'Saturday the tenth. From 22:00 to midnight UTC, Amamake lost 690 ships. 1,056 pilots were on the mails. Most of the hulls were not militia ships. Minmatar Fleet formed for the birthday brawl. The rest of the grid was nullsec.',
            'A Hel died at 23:14, 53 billion, flown for Cryonic Origin. A Vehement died at 22:52. A Valravn died at 23:24 for Warlock Industries. Phoenix Navy Issues, Revelations, and Naglfars went with them. Sigma Grindset and The Obsidian Front lost dreadnoughts. So did Minmatar Fleet.',
        ],
        ships: 690,
        isk: 460_686_072_593,
        unique_pilots: 1_056,
        flip_label: '10 Oct',
        minmatar_pilots: 117,
        minmatar_ships: 114,
        amarr_pilots: 20,
        amarr_ships: 14,
        amarr_isk: 644_761_309,
        minmatar_isk: 121_209_795_727,
        other_ships: 562,
        other_isk: 338_831_515_557,
        engagement_mix: [
            { label: 'Fleet (11+)', value: 568 },
            { label: 'Small gang (2–10)', value: 111 },
            { label: 'Solo', value: 11 },
        ],
        small_gang_kills: 111,
        closing: 'GFs all, until the next one.',
        links: [
            { href: AMAMAKE_ZKILL, label: 'Amamake on zKillboard' },
        ],
        campaign_path: AMAMAKE_ZKILL,
    },
    fleet: {
        tracked_fleets: 0,
        untracked_forms_lower_bound: 0,
        largest_public_pickup: 0,
        dek: 'The public formup was the 10 Oct Amamake birthday brawl. Character-level boards and Discord ping internals stay off this page.',
    },
    pilots: {
        scope: 'Killmails appeared on as attacker across the warzone systems in October, from zKillboard. Solo is only one character on the killmail. Small gang, 2-10 pilots. Fleets have 25+ characters involved.',
        boards: [
            { title: 'Solo', minmatar: MINMATAR_SOLO, amarr: AMARR_SOLO },
            { title: 'Small gang', minmatar: MINMATAR_SMALL_GANG, amarr: AMARR_SMALL_GANG },
            { title: 'Fleets', minmatar: MINMATAR_FLEET, amarr: AMARR_FLEET },
        ],
    },
    top_ships: {
        boards: [
            { title: 'Solo', ships: SHIPS_SOLO },
            { title: 'Small gang', ships: SHIPS_SMALL_GANG },
            { title: 'Fleets', ships: SHIPS_FLEET },
        ],
    },
    groups: {
        scope: 'Alliances, or corporations flying without one, ranked by killmails in the warzone. Only groups with more than half of their October kills inside the warzone are listed, so nullsec blocs passing through do not crowd out the people who live here.',
        rows: GROUPS,
    },
    get_involved: {
        steps: [
            {
                title: 'Buy a Ship',
                text: 'A Thrasher or a Punisher is enough to start. Amamake, the freeport in the middle of the warzone, is where both militias shop for hulls and fits.',
                href: '/learning/guides/navy-frigate-guide/',
                label: 'Starter hulls',
            },
            {
                title: 'Run a Complex',
                text: 'A complex is a site. Run it and the contested bar moves; at 100% the system can change hands. Most of the fighting is still small gang and solo.',
                href: '/learning/guides/faction-warfare-plexing/',
                label: 'How plexing works',
            },
            {
                title: 'Join a Fleet',
                text: 'Minmatar Fleet forms every day across all timezones, with public pickups on the big pushes. Hop in a fleet and you are never far from a fight.',
                href: '/learning/guides/new-player-fleet-guide/',
                label: 'Your first fleet',
            },
        ],
        actions: [
            { href: 'https://discord.com/invite/3hZfahmkFx', label: 'Join Militia Discord' },
        ],
        featured_guides: [
            'faction-warfare-basics',
            'navy-destroyer-metagame',
            'navy-frigate-guide',
        ],
    },
    methodology: [
        {
            label: 'Destruction',
            text: 'Every ship kill in the Amarr–Minmatar faction-warfare systems for the month, from zKillboard, with capsules and NPC-only kills removed.',
        },
        {
            label: 'Month over month',
            text: 'Deltas compare the same measure against the prior month.',
        },
        {
            label: 'Rankings',
            text: 'Pilots, ships, and groups are ranked by killmails in those systems.',
        },
        {
            label: 'Standings',
            text: 'Systems held is the month-end count, scored from Dotlan occupancy history. Enlisted pilots, and kills and victory points, are live empire-wide ESI figures from the most recent week.',
        },
        {
            label: 'Occupancy',
            text: 'Scored from Dotlan system history; the holder shown for each system is its live ESI occupier.',
        },
    ],
}
