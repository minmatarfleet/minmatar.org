import {
    AMARR_DESTROYED_ISK,
    AMARR_DESTROYED_SHIPS,
    AMARR_PILOTS,
    CAMPAIGN_ISK_DESTROYED,
    CANONICAL_PATH as AUGA_CANONICAL_PATH,
    ENGAGEMENT_MIX,
    MINMATAR_DESTROYED_ISK,
    MINMATAR_DESTROYED_SHIPS,
    MINMATAR_PILOTS,
    OTHER_DESTROYED_ISK,
    OTHER_DESTROYED_SHIPS,
    SHIPS_DESTROYED as AUGA_SIEGE_SHIPS,
    UNIQUE_PILOTS as AUGA_UNIQUE_PILOTS,
} from '@/data/campaigns/auga'

import type { WarzoneIssue } from './types'
import {
    AMARR_FLEET,
    AMARR_SMALL_GANG,
    AMARR_SOLO,
    BOARDS_SAMPLED_KILLS,
    BOARDS_TOTAL_ISK,
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
} from './yc128-07-boards'

export const SLUG = 'yc128-07' as const
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

export const YC128_07: WarzoneIssue = {
    slug: SLUG,
    permalink_path: PERMALINK_PATH,
    cover_image: COVER_IMAGE,
    published_at: new Date('2026-07-31T00:00:00Z'),
    period_utc: '1–31 Jul 2026 UTC',
    previous_period_label: 'June',
    esi_as_of: '4 Sep 2026',
    who_won: 'Amarr took three. Hed did the dying.',
    opening:
        'The map moved on the Minmatar front. Amarr kept the systems they took. Hed still printed the killmails. The week that traveled was a siege in Auga — that is the focus below, not the scoreboard.',
    sampled_ships: BOARDS_SAMPLED_KILLS,
    sampled_isk: BOARDS_TOTAL_ISK,
    focus_name: 'Auga',
    occupancy_changes: 5,
    occupancy_net_amarr: 3,
    systems_that_moved: 4,
    occupancy_dek:
        'Amarr took four and gave one back. All five changes were on the Minmatar front — Hed and Metropolis. The Amarr home front did not change hands.',
    scoreboard: [
        {
            militia: 'minmatar',
            occupancy_net: -3,
            systems_held: SCOREBOARD_STATS.minmatar.systems,
            enlisted_pilots: SCOREBOARD_STATS.minmatar.pilots,
            enlisted_pilots_label: count_label(SCOREBOARD_STATS.minmatar.pilots),
            active_pilots: SCOREBOARD_STATS.minmatar.active_pilots,
            active_pilots_label: SCOREBOARD_STATS.minmatar.active_pilots.toLocaleString('en-US'),
            kills_last_week: SCOREBOARD_STATS.minmatar.kills,
            victory_points_last_week: SCOREBOARD_STATS.minmatar.victory_points_last_week,
            victory_points_last_week_label: count_label(SCOREBOARD_STATS.minmatar.victory_points_last_week),
        },
        {
            militia: 'amarr',
            occupancy_net: 3,
            systems_held: SCOREBOARD_STATS.amarr.systems,
            enlisted_pilots: SCOREBOARD_STATS.amarr.pilots,
            enlisted_pilots_label: count_label(SCOREBOARD_STATS.amarr.pilots),
            active_pilots: SCOREBOARD_STATS.amarr.active_pilots,
            active_pilots_label: SCOREBOARD_STATS.amarr.active_pilots.toLocaleString('en-US'),
            kills_last_week: SCOREBOARD_STATS.amarr.kills,
            victory_points_last_week: SCOREBOARD_STATS.amarr.victory_points_last_week,
            victory_points_last_week_label: count_label(SCOREBOARD_STATS.amarr.victory_points_last_week),
        },
    ],
    fights: [
        {
            system: 'Amamake',
            date_label: '12 Jul',
            dek: 'Hed’s freeport is a market and a killboard. On the twelfth it was both: a public DNG birthday brawl on video, and later an r/Eve post that treated the shop as the story. Loudest system in the warzone all month.',
            ships: system_stat('Amamake').ships,
            isk_label: system_stat('Amamake').isk_label,
            vs_last_month: system_stat('Amamake').vs_last_month,
            links: [
                { href: 'https://zkillboard.com/system/30002537/', label: 'zKill' },
                { href: 'https://youtu.be/6OZd594h2CM', label: 'Video' },
                {
                    href: 'https://www.reddit.com/r/Eve/comments/1uy7sl0/extra_extra_the_rats_are_back_to_amamake_rip_dng/',
                    label: 'r/Eve thread',
                },
            ],
        },
    ],
    occupancy: [
        {
            date_label: '18 Jul',
            system: 'Auga',
            taken_by: 'minmatar',
            ships: system_stat('Auga').ships,
            vs_last_month: system_stat('Auga').vs_last_month,
            isk_label: system_stat('Auga').isk_label,
            holds_today: system_stat('Auga').holds_today,
            dotlan_href: 'https://evemaps.dotlan.net/system/Auga',
            zkill_href: 'https://zkillboard.com/system/30002542/',
        },
        {
            date_label: '5 Jul',
            system: 'Eszur',
            taken_by: 'amarr',
            ships: system_stat('Eszur').ships,
            vs_last_month: system_stat('Eszur').vs_last_month,
            isk_label: system_stat('Eszur').isk_label,
            holds_today: system_stat('Eszur').holds_today,
            dotlan_href: 'https://evemaps.dotlan.net/system/Eszur',
            zkill_href: 'https://zkillboard.com/system/30002095/',
        },
        {
            date_label: '6 Jul',
            system: 'Hadozeko',
            taken_by: 'amarr',
            ships: system_stat('Hadozeko').ships,
            vs_last_month: system_stat('Hadozeko').vs_last_month,
            isk_label: system_stat('Hadozeko').isk_label,
            holds_today: system_stat('Hadozeko').holds_today,
            dotlan_href: 'https://evemaps.dotlan.net/system/Hadozeko',
            zkill_href: 'https://zkillboard.com/system/30002057/',
        },
        {
            date_label: '8 Jul',
            system: 'Lantorn',
            taken_by: 'amarr',
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
        'Busiest systems by ships destroyed in July, across all 70 warzone systems. Source: zKillboard per-system API, capsules removed.',
    fronts: [
        {
            name: 'Minmatar front',
            regions: 'Heimatar and Metropolis',
            occupancy_label: '5 occupancy changes',
            ships: FRONTS.minmatar.ships,
            ships_label: FRONTS.minmatar.ships_label,
            hottest_system: FRONTS.minmatar.hottest_system,
            dek: 'Heimatar and Metropolis. This is where the war is actually fought — the large majority of the month\'s ship kills fell here, led by Amamake and Auga. Every occupancy change in July was on this front.',
        },
        {
            name: 'Amarr front',
            regions: 'Devoid and The Bleak Lands',
            occupancy_label: 'no occupancy changes',
            ships: FRONTS.amarr.ships,
            ships_label: FRONTS.amarr.ships_label,
            hottest_system: FRONTS.amarr.hottest_system,
            dek: 'Devoid and The Bleak Lands. Quieter by an order of magnitude, with Kourmonen the one real hotspot as the fight spills over from Hed next door. No system changed hands here in July.',
        },
    ],
    focus: {
        title: 'Auga siege',
        window_label: '12–18 Jul',
        dek: [
            'Cradle of War landed in June. By mid-July the new complexes were a reason to stay after the first brawl. The sites pay. The bar moves. Someone has to be plexing at downtime.',
            'Amarr took Auga on 4 Jul. They still held it on the seventeenth — after a 171-pilot Minmatar Fleet pickup, after an Amarr Revelation went down. On the morning of the eighteenth Twan Molenaar called the flip. The same morning that alliance formed for Kourmonen.',
            `Minmatar lost ${(MINMATAR_DESTROYED_ISK / 1_000_000_000).toFixed(2)}B on that field; Amarr lost ${(AMARR_DESTROYED_ISK / 1_000_000_000).toFixed(2)}B. Empyrean Edict and Slide On Contact put the heaviest Amarr boards there. Minmatar Fleet was the largest alliance on the mails, which also means they took the heaviest losses. A hundred and fourteen Angels showed up to farm the wrecks. Most of the week was not a fleet: 869 small gang, 486 solo, 226 fleet (11+). The hulls that died were the hulls of the warzone after Uprising: Thrasher Fleet Issue, T1 Thrasher, Rifter, then navy cruisers; Amarr answered Punisher and Slicer; Gallente navy showed up anyway.`,
        ],
        ships: AUGA_SIEGE_SHIPS,
        isk: CAMPAIGN_ISK_DESTROYED,
        unique_pilots: AUGA_UNIQUE_PILOTS,
        flip_label: '18 Jul',
        minmatar_pilots: MINMATAR_PILOTS,
        minmatar_ships: MINMATAR_DESTROYED_SHIPS,
        amarr_pilots: AMARR_PILOTS,
        amarr_ships: AMARR_DESTROYED_SHIPS,
        amarr_isk: AMARR_DESTROYED_ISK,
        minmatar_isk: MINMATAR_DESTROYED_ISK,
        other_ships: OTHER_DESTROYED_SHIPS,
        other_isk: OTHER_DESTROYED_ISK,
        engagement_mix: ENGAGEMENT_MIX,
        small_gang_kills: SMALL_GANG?.value ?? 869,
        closing: 'A flip is a week. A front is a year.',
        links: [
            {
                href: 'https://br.evetools.org/related/30002542/202607141800',
                label: '14 Jul, 18:00 EUTZ · 45 kills, 16.71B',
            },
            {
                href: 'https://br.evetools.org/related/30002542/202607171743',
                label: '17 Jul round · 47 kills, 80 pilots',
            },
            {
                href: 'https://zkillboard.com/kill/137030626/',
                label: 'Revelation',
            },
        ],
        campaign_path: AUGA_CANONICAL_PATH,
    },
    fleet: {
        tracked_fleets: 64,
        untracked_forms_lower_bound: 15,
        largest_public_pickup: 171,
        dek: 'Public windows included a 171-pilot pickup on 16 Jul, the Kourmonen form the morning of the Auga flip, and a Dal battlefield on the 22nd. Character-level boards and Discord ping internals stay off this page.',
    },
    pilots: {
        scope: 'Killmails appeared on as attacker across the warzone systems in July, from zKillboard. Solo is one pilot on the mail, small gang two to twenty-four, fleet twenty-five or more. Affiliation is the group each pilot flew with most.',
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
        scope: 'Alliances, or corporations flying without one, ranked by killmails in the warzone. Only groups with more than half of their July kills inside the warzone are listed, so nullsec blocs passing through do not crowd out the people who live here.',
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
    methodology:
        'Destruction figures count every ship kill in the Amarr–Minmatar faction-warfare systems for the month, from zKillboard, with capsules and NPC-only kills removed; month-over-month figures compare the same measure against the prior month. Pilots, ships, and groups are ranked by killmails in those systems. Systems held, enlisted pilots, and kills and victory points are live empire-wide ESI standings. Occupancy is scored from Dotlan system history; the holder shown for each system is its live ESI occupier.',
}
