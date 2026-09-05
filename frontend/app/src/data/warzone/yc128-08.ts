import {
    AAR_URL,
    AMARR_DESTROYED_ISK,
    AMARR_DESTROYED_SHIPS,
    AMARR_PILOTS,
    BATTLE_REPORT_URL,
    CAMPAIGN_ISK_DESTROYED,
    ENGAGEMENT_MIX,
    MINMATAR_DESTROYED_ISK,
    MINMATAR_DESTROYED_SHIPS,
    MINMATAR_PILOTS,
    OTHER_DESTROYED_ISK,
    OTHER_DESTROYED_SHIPS,
    SHIPS_DESTROYED as KAMELA_SHIPS,
    UNIQUE_PILOTS as KAMELA_UNIQUE_PILOTS,
    WINDOW_LABEL as KAMELA_WINDOW,
    ZKILL_SYSTEM_URL as KAMELA_ZKILL,
} from '@/data/campaigns/kamela'

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
} from './yc128-08-boards'

export const SLUG = 'yc128-08' as const
export const PERMALINK_PATH = `/warzone/${SLUG}/` as const
export const LATEST_PATH = '/warzone/' as const
export const COVER_IMAGE = '/images/warzone-cover.jpg'

const SMALL_GANG = ENGAGEMENT_MIX.find((row) => row.label.startsWith('Small gang'))

/** Compact count label: 1_118_133 -> "1.12M", 34_527 -> "34.5k". */
function count_label(value: number): string {
    if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(2)}M`
    if (value >= 1_000) return `${(value / 1_000).toFixed(1)}k`
    return String(value)
}

const STAT_BY_NAME = new Map(SYSTEM_STATS.map((row) => [row.system, row]))
function system_stat(name: string) {
    const row = STAT_BY_NAME.get(name)
    if (!row) throw new Error(`No warzone stats for system ${name}`)
    return row
}

export const YC128_08: WarzoneIssue = {
    slug: SLUG,
    permalink_path: PERMALINK_PATH,
    cover_image: COVER_IMAGE,
    published_at: new Date('2026-08-31T00:00:00Z'),
    period_utc: '1–31 Aug 2026 UTC',
    previous_period_label: 'July',
    esi_as_of: '4 Sep 2026',
    who_won: 'Minmatar pushed south. Kamela cost 350 billion.',
    opening:
        'Minmatar Fleet is back in faction warfare full time, and in August the map moved the other way. The push went onto the Amarr home front — Kourmonen and Kamela both flipped, the first Minmatar gains in The Bleak Lands in months. Then the Kamela Fortizar timer turned into the biggest brawl of the month: 350 billion ISK on one field. That fight is the focus below.',
    sampled_ships: BOARDS_SAMPLED_KILLS,
    sampled_isk: BOARDS_TOTAL_ISK,
    sampled_ships_vs: BOARDS_SAMPLED_KILLS_VS,
    sampled_isk_vs: BOARDS_TOTAL_ISK_VS,
    focus_name: 'Kamela',
    occupancy_changes: 4,
    occupancy_net_amarr: -3,
    systems_that_moved: 3,
    occupancy_dek:
        'Minmatar took three and gave none back. Two were on the Amarr home front — Kourmonen and Kamela in The Bleak Lands — the deepest the militia has pushed south all year. Kamela changed hands twice in two days, passing briefly through Angel Cartel before Minmatar took it.',
    scoreboard: [
        {
            militia: 'minmatar',
            occupancy_net: 3,
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
            occupancy_net: -3,
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
            system: 'Kourmonen',
            date_label: '14 Aug',
            dek: 'The staging point for the push south. Kourmonen was the busiest system on the Amarr home front all month and the second-loudest in the warzone — the grind that opened the road to Kamela before it flipped Minmatar on the fourteenth.',
            ships: system_stat('Kourmonen').ships,
            isk_label: system_stat('Kourmonen').isk_label,
            vs_last_month: system_stat('Kourmonen').vs_last_month,
            links: [
                { href: 'https://zkillboard.com/system/30003068/', label: 'zKill' },
            ],
        },
    ],
    occupancy: [
        {
            date_label: '13 Aug',
            system: 'Kamela',
            taken_by: 'minmatar',
            ships: system_stat('Kamela').ships,
            vs_last_month: system_stat('Kamela').vs_last_month,
            isk_label: system_stat('Kamela').isk_label,
            holds_today: system_stat('Kamela').holds_today,
            dotlan_href: 'https://evemaps.dotlan.net/system/Kamela',
            zkill_href: 'https://zkillboard.com/system/30003069/',
        },
        {
            date_label: '14 Aug',
            system: 'Kourmonen',
            taken_by: 'minmatar',
            ships: system_stat('Kourmonen').ships,
            vs_last_month: system_stat('Kourmonen').vs_last_month,
            isk_label: system_stat('Kourmonen').isk_label,
            holds_today: system_stat('Kourmonen').holds_today,
            dotlan_href: 'https://evemaps.dotlan.net/system/Kourmonen',
            zkill_href: 'https://zkillboard.com/system/30003068/',
        },
        {
            date_label: '15 Aug',
            system: 'Lantorn',
            taken_by: 'minmatar',
            ships: system_stat('Lantorn').ships,
            vs_last_month: system_stat('Lantorn').vs_last_month,
            isk_label: system_stat('Lantorn').isk_label,
            holds_today: system_stat('Lantorn').holds_today,
            dotlan_href: 'https://evemaps.dotlan.net/system/Lantorn',
            zkill_href: 'https://zkillboard.com/system/30002540/',
        },
    ],
    traffic: TRAFFIC,
    traffic_footnote:
        'Busiest systems by ships destroyed in August, across all 70 warzone systems. Source: zKillboard per-system API, capsules removed.',
    fronts: [
        {
            name: 'Minmatar front',
            regions: 'Heimatar and Metropolis',
            occupancy_label: '1 occupancy change',
            ships: FRONTS.minmatar.ships,
            ships_label: FRONTS.minmatar.ships_label,
            ships_vs: FRONTS.minmatar.ships_vs,
            hottest_system: FRONTS.minmatar.hottest_system,
            dek: 'Heimatar and Metropolis. Still where most of the war is fought — Amamake led the warzone again by a wide margin, and Auga stayed loud after July\'s siege. Lantorn was the one system to change hands here, flipping back to Minmatar.',
        },
        {
            name: 'Amarr front',
            regions: 'Devoid and The Bleak Lands',
            occupancy_label: '2 occupancy changes',
            ships: FRONTS.amarr.ships,
            ships_label: FRONTS.amarr.ships_label,
            ships_vs: FRONTS.amarr.ships_vs,
            hottest_system: FRONTS.amarr.hottest_system,
            dek: 'Devoid and The Bleak Lands. Normally the quiet front — but this month the war came here. Kourmonen and Kamela both flipped to Minmatar, and Kamela alone burned 474B in ships as the militia pushed toward Sosala.',
        },
    ],
    focus: {
        title: 'Kamela: 350B down',
        window_label: KAMELA_WINDOW,
        section_dek:
            'One story that would not fit a normal issue: the night the push south turned into a 350-billion-ISK brawl over the Kamela Fortizar.',
        cta_label: 'Read the full AAR',
        dek: [
            'Minmatar Fleet is back in faction warfare full time, and the campaign this summer has been a march south — Auga, Kourmonen, Kamela, and one day the holy land, Sosala. With docking secured, the point of tension became the Kamela Fortizar, which the militia reinforced again and again.',
            'CVA got tired of the rats gnawing at the walls. On the twenty-ninth the timer finally broke into a real fight: FL33T bridged in Tempest Fleet Issues and guardians, CVA and RMC landed at zero, and both sides started throwing dreads. FL33T ran cheap T1 Revelations by the dozen; CVA answered with better-fit capitals. Seventeen dreadnoughts died on the field.',
            `Then everyone else arrived. CAMELOT tornadoes, INIT zealots and Kikimoras, Sedition and BIGAB Barghests, BRAVE, AHBA, SRS — a dozen groups piling onto a lowsec grid. When the smoke cleared, ${KAMELA_SHIPS} ships and ${(CAMPAIGN_ISK_DESTROYED / 1_000_000_000).toFixed(0)}B ISK were gone and ${KAMELA_UNIQUE_PILOTS.toLocaleString('en-US')} pilots had been on grid. Third parties did most of the dying; CVA took the worst of the two principals. Kamela stayed Minmatar.`,
        ],
        ships: KAMELA_SHIPS,
        isk: CAMPAIGN_ISK_DESTROYED,
        unique_pilots: KAMELA_UNIQUE_PILOTS,
        flip_label: '13 Aug',
        minmatar_pilots: MINMATAR_PILOTS,
        minmatar_ships: MINMATAR_DESTROYED_SHIPS,
        amarr_pilots: AMARR_PILOTS,
        amarr_ships: AMARR_DESTROYED_SHIPS,
        amarr_isk: AMARR_DESTROYED_ISK,
        minmatar_isk: MINMATAR_DESTROYED_ISK,
        other_ships: OTHER_DESTROYED_SHIPS,
        other_isk: OTHER_DESTROYED_ISK,
        engagement_mix: ENGAGEMENT_MIX,
        small_gang_kills: SMALL_GANG?.value ?? 103,
        closing: 'GFs all, until the next one.',
        links: [
            { href: AAR_URL, label: 'AAR: 350b down in Kamela' },
            { href: BATTLE_REPORT_URL, label: '29 Aug, 19:00 — peak-hour battle report' },
            { href: KAMELA_ZKILL, label: 'Kamela on zKillboard' },
        ],
        campaign_path: AAR_URL,
    },
    fleet: {
        tracked_fleets: 60,
        untracked_forms_lower_bound: 15,
        largest_public_pickup: 179,
        dek: 'Public windows centered on the Kamela Fortizar timers through mid-to-late August, peaking with the 29 Aug brawl. Character-level boards and Discord ping internals stay off this page.',
    },
    pilots: {
        scope: 'Killmails appeared on as attacker across the warzone systems in August, from zKillboard. Solo is only one character on the killmail. Small gang, 2-10 pilots. Fleets have 25+ characters involved.',
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
        scope: 'Alliances, or corporations flying without one, ranked by killmails in the warzone. Only groups with more than half of their August kills inside the warzone are listed, so nullsec blocs passing through do not crowd out the people who live here.',
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
