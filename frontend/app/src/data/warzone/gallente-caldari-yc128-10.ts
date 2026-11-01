import type { WarzoneIssue } from './types'
import {
    BOARDS_SAMPLED_KILLS,
    BOARDS_TOTAL_ISK,
    CALDARI_FLEET,
    CALDARI_SMALL_GANG,
    CALDARI_SOLO,
    FRONTS,
    GALLENTE_FLEET,
    GALLENTE_SMALL_GANG,
    GALLENTE_SOLO,
    GROUPS,
    SCOREBOARD_STATS,
    SHIPS_FLEET,
    SHIPS_SMALL_GANG,
    SHIPS_SOLO,
    SYSTEM_STATS,
    TRAFFIC,
} from './gallente-caldari-yc128-10-boards'

export const SLUG = 'gallente-caldari-yc128-10' as const
export const PERMALINK_PATH = `/warzone/${SLUG}/` as const
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

function occupancy_row(
    date_label: string,
    system: SystemName,
    taken_by: 'gallente' | 'caldari',
    previous_owner: 'gallente' | 'caldari' | 'guristas',
) {
    const stat = system_stat(system)
    return {
        date_label,
        system,
        taken_by,
        previous_owner,
        ships: stat.ships,
        vs_last_month: stat.vs_last_month,
        isk_label: stat.isk_label,
        holds_today: stat.holds_today,
        dotlan_href: `https://evemaps.dotlan.net/system/${system}`,
        zkill_href: `https://zkillboard.com/system/${stat.system_id}/`,
    }
}

export const GALLENTE_CALDARI_YC128_10: WarzoneIssue = {
    slug: SLUG,
    permalink_path: PERMALINK_PATH,
    cover_image: COVER_IMAGE,
    published_at: new Date('2026-10-31T00:00:00Z'),
    period_utc: '1–31 Oct 2026 UTC',
    previous_period_label: 'September',
    esi_as_of: '1 Nov 2026',
    zone: 'gallente-caldari',
    show_deltas: false,
    who_won: 'Caldari took five systems. Tama cost 240 billion.',
    opening:
        'October ended 27 systems Gallente, 63 Caldari. Caldari took Anchauttes, Aubenall, Esesier, Eugales, Frarie, Hasmijaala, and Moclinamaud. Gallente took Kedama and Nisuwa, and finished holding Alparena, which started the month with the Guristas. Tama was Gallente from the ninth and Caldari again on the thirty-first. Aldranette was the loudest Gallente system. Tama was the loudest on the Caldari side.',
    sampled_ships: BOARDS_SAMPLED_KILLS,
    sampled_isk: BOARDS_TOTAL_ISK,
    occupancy_changes: 23,
    occupancy_net_amarr: 0,
    systems_that_moved: 10,
    occupancy_dek:
        'Ten systems finished in new hands, and the month ended 27 Gallente, 63 Caldari. Caldari took seven. Gallente took Kedama and Nisuwa. Alparena started with the Guristas, spent most of the month Caldari, and finished Gallente on the twenty-ninth. Tama, Hysera, and Odamia changed hands and ended where they began. Tama was back in Caldari hands on the thirty-first.',
    scoreboard: [
        {
            militia: 'gallente',
            occupancy_net: -4,
            systems_held: SCOREBOARD_STATS.gallente.systems,
            enlisted_pilots: SCOREBOARD_STATS.gallente.pilots,
            enlisted_pilots_label: count_label(SCOREBOARD_STATS.gallente.pilots),
            active_pilots: SCOREBOARD_STATS.gallente.active_pilots,
            active_pilots_label: SCOREBOARD_STATS.gallente.active_pilots.toLocaleString('en-US'),
            kills: SCOREBOARD_STATS.gallente.kills,
            victory_points_last_week: SCOREBOARD_STATS.gallente.victory_points_last_week,
            victory_points_last_week_label: count_label(SCOREBOARD_STATS.gallente.victory_points_last_week),
        },
        {
            militia: 'caldari',
            occupancy_net: 5,
            systems_held: SCOREBOARD_STATS.caldari.systems,
            enlisted_pilots: SCOREBOARD_STATS.caldari.pilots,
            enlisted_pilots_label: count_label(SCOREBOARD_STATS.caldari.pilots),
            active_pilots: SCOREBOARD_STATS.caldari.active_pilots,
            active_pilots_label: SCOREBOARD_STATS.caldari.active_pilots.toLocaleString('en-US'),
            kills: SCOREBOARD_STATS.caldari.kills,
            victory_points_last_week: SCOREBOARD_STATS.caldari.victory_points_last_week,
            victory_points_last_week_label: count_label(SCOREBOARD_STATS.caldari.victory_points_last_week),
        },
    ],
    fights: [],
    occupancy: [
        occupancy_row('16 Oct', 'Aubenall', 'caldari', 'gallente'),
        occupancy_row('16 Oct', 'Kedama', 'gallente', 'caldari'),
        occupancy_row('18 Oct', 'Moclinamaud', 'caldari', 'gallente'),
        occupancy_row('21 Oct', 'Anchauttes', 'caldari', 'gallente'),
        occupancy_row('22 Oct', 'Eugales', 'caldari', 'gallente'),
        occupancy_row('23 Oct', 'Esesier', 'caldari', 'gallente'),
        occupancy_row('23 Oct', 'Frarie', 'caldari', 'gallente'),
        occupancy_row('24 Oct', 'Nisuwa', 'gallente', 'caldari'),
        occupancy_row('29 Oct', 'Alparena', 'gallente', 'caldari'),
        occupancy_row('30 Oct', 'Hasmijaala', 'caldari', 'gallente'),
    ],
    traffic: TRAFFIC,
    traffic_footnote:
        'Busiest systems by ships destroyed in October, across all 90 warzone systems. Source: zKillboard per-system API, capsules removed.',
    fronts: [
        {
            name: 'Gallente front',
            regions: 'Placid, Essence, and Verge Vendor',
            occupancy_label: '14 occupancy changes',
            ships: FRONTS.gallente.ships,
            ships_label: FRONTS.gallente.ships_label,
            hottest_system: FRONTS.gallente.hottest_system,
            dek: 'Placid, Essence, and Verge Vendor. Aldranette led this side, 285 billion destroyed. Fourteen systems changed hands here. Caldari took Anchauttes, Aubenall, Esesier, Eugales, Frarie, and Moclinamaud. Alparena finished with Gallente after opening the month under the Guristas.',
        },
        {
            name: 'Caldari front',
            regions: 'Black Rise and The Citadel',
            occupancy_label: '9 occupancy changes',
            ships: FRONTS.caldari.ships,
            ships_label: FRONTS.caldari.ships_label,
            hottest_system: FRONTS.caldari.hottest_system,
            dek: 'Black Rise and The Citadel. Tama led the warzone, 240 billion, Gallente from the ninth and Caldari again on the thirty-first. Nine systems changed hands here. Gallente took Kedama and Nisuwa. Caldari took Hasmijaala. Hysera flipped and flipped back.',
        },
    ],
    fleet: {
        tracked_fleets: 0,
        untracked_forms_lower_bound: 0,
        largest_public_pickup: 0,
        dek: 'No single public formup is called out this month. Character-level boards and Discord ping internals stay off this page.',
    },
    pilots: {
        scope: 'Killmails appeared on as attacker across the warzone systems in October, from zKillboard. Solo is only one character on the killmail. Small gang, 2-10 pilots. Fleets have 25+ characters involved.',
        boards: [
            { title: 'Solo', gallente: GALLENTE_SOLO, caldari: CALDARI_SOLO },
            { title: 'Small gang', gallente: GALLENTE_SMALL_GANG, caldari: CALDARI_SMALL_GANG },
            { title: 'Fleets', gallente: GALLENTE_FLEET, caldari: CALDARI_FLEET },
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
                text: 'A Tristan or a Hookbill is enough to start. Tama, Aldranette, and Heydieles are where most of the hulls die.',
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
                text: 'Public fleets run on both sides of this warzone. Hop in a fleet and you are never far from a fight.',
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
            text: 'Every ship kill in the Gallente–Caldari faction-warfare systems for the month, from zKillboard, with capsules and NPC-only kills removed.',
        },
        {
            label: 'Month over month',
            text: 'This is the first Gallente–Caldari issue, so there is no prior month to compare. The arrows stay off.',
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
