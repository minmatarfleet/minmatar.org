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
    SHIPS_DESTROYED as AMAMAKE_SHIPS,
    UNIQUE_PILOTS as AMAMAKE_UNIQUE_PILOTS,
    WINDOW_LABEL as AMAMAKE_WINDOW,
    ZKILL_SYSTEM_URL as AMAMAKE_ZKILL,
} from '@/data/campaigns/amamake-brawl'

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
} from './yc128-09-boards'

export const SLUG = 'yc128-09' as const
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

export const YC128_09: WarzoneIssue = {
    slug: SLUG,
    permalink_path: PERMALINK_PATH,
    cover_image: COVER_IMAGE,
    published_at: new Date('2026-09-30T00:00:00Z'),
    period_utc: '1–30 Sep 2026 UTC',
    previous_period_label: 'August',
    esi_as_of: '1 Oct 2026',
    who_won: 'Amarr took the south back. Amamake cost 625 billion.',
    opening:
        'September ended on the same split August left: 26 systems Minmatar, 44 Amarr. The systems were different ones. Amarr took Kamela and Kourmonen back. Minmatar took Eszur, Ebolfer, Hadozeko, and Ontorn. On the twenty-sixth Amamake threw a birthday brawl, and a titan died at the sun. That night is the focus below.',
    sampled_ships: BOARDS_SAMPLED_KILLS,
    sampled_isk: BOARDS_TOTAL_ISK,
    sampled_ships_vs: BOARDS_SAMPLED_KILLS_VS,
    sampled_isk_vs: BOARDS_TOTAL_ISK_VS,
    focus_name: 'Amamake',
    occupancy_changes: 14,
    occupancy_net_amarr: 0,
    systems_that_moved: 8,
    occupancy_dek:
        'Eight systems finished in new hands, and the month still ended 26 Minmatar, 44 Amarr. Amarr took back Kamela and Kourmonen. Minmatar took Eszur, Ebolfer, Hadozeko, and Ontorn, and gave up Lantorn and Todifrauan. Klogori and Oyonata changed hands and changed back. Oyonata spent a day with the Angel Cartel on the way.',
    scoreboard: [
        {
            militia: 'minmatar',
            occupancy_net: 0,
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
            occupancy_net: 0,
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
            date_label: '28 Sep',
            dek: 'The beachhead from August. Kourmonen was the loudest system on the Amarr home front all month, and it flipped back to Amarr on the twenty-eighth.',
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
            date_label: '1 Sep',
            system: 'Eszur',
            taken_by: 'minmatar',
            ships: system_stat('Eszur').ships,
            vs_last_month: system_stat('Eszur').vs_last_month,
            isk_label: system_stat('Eszur').isk_label,
            holds_today: system_stat('Eszur').holds_today,
            dotlan_href: 'https://evemaps.dotlan.net/system/Eszur',
            zkill_href: 'https://zkillboard.com/system/30002095/',
        },
        {
            date_label: '14 Sep',
            system: 'Lantorn',
            taken_by: 'amarr',
            ships: system_stat('Lantorn').ships,
            vs_last_month: system_stat('Lantorn').vs_last_month,
            isk_label: system_stat('Lantorn').isk_label,
            holds_today: system_stat('Lantorn').holds_today,
            dotlan_href: 'https://evemaps.dotlan.net/system/Lantorn',
            zkill_href: 'https://zkillboard.com/system/30002540/',
        },
        {
            date_label: '16 Sep',
            system: 'Ebolfer',
            taken_by: 'minmatar',
            ships: system_stat('Ebolfer').ships,
            vs_last_month: system_stat('Ebolfer').vs_last_month,
            isk_label: system_stat('Ebolfer').isk_label,
            holds_today: system_stat('Ebolfer').holds_today,
            dotlan_href: 'https://evemaps.dotlan.net/system/Ebolfer',
            zkill_href: 'https://zkillboard.com/system/30002094/',
        },
        {
            date_label: '17 Sep',
            system: 'Kamela',
            taken_by: 'amarr',
            ships: system_stat('Kamela').ships,
            vs_last_month: system_stat('Kamela').vs_last_month,
            isk_label: system_stat('Kamela').isk_label,
            holds_today: system_stat('Kamela').holds_today,
            dotlan_href: 'https://evemaps.dotlan.net/system/Kamela',
            zkill_href: 'https://zkillboard.com/system/30003069/',
        },
        {
            date_label: '17 Sep',
            system: 'Hadozeko',
            taken_by: 'minmatar',
            ships: system_stat('Hadozeko').ships,
            vs_last_month: system_stat('Hadozeko').vs_last_month,
            isk_label: system_stat('Hadozeko').isk_label,
            holds_today: system_stat('Hadozeko').holds_today,
            dotlan_href: 'https://evemaps.dotlan.net/system/Hadozeko',
            zkill_href: 'https://zkillboard.com/system/30002057/',
        },
        {
            date_label: '22 Sep',
            system: 'Ontorn',
            taken_by: 'minmatar',
            ships: system_stat('Ontorn').ships,
            vs_last_month: system_stat('Ontorn').vs_last_month,
            isk_label: system_stat('Ontorn').isk_label,
            holds_today: system_stat('Ontorn').holds_today,
            dotlan_href: 'https://evemaps.dotlan.net/system/Ontorn',
            zkill_href: 'https://zkillboard.com/system/30002091/',
        },
        {
            date_label: '25 Sep',
            system: 'Todifrauan',
            taken_by: 'amarr',
            ships: system_stat('Todifrauan').ships,
            vs_last_month: system_stat('Todifrauan').vs_last_month,
            isk_label: system_stat('Todifrauan').isk_label,
            holds_today: system_stat('Todifrauan').holds_today,
            dotlan_href: 'https://evemaps.dotlan.net/system/Todifrauan',
            zkill_href: 'https://zkillboard.com/system/30002062/',
        },
        {
            date_label: '28 Sep',
            system: 'Kourmonen',
            taken_by: 'amarr',
            ships: system_stat('Kourmonen').ships,
            vs_last_month: system_stat('Kourmonen').vs_last_month,
            isk_label: system_stat('Kourmonen').isk_label,
            holds_today: system_stat('Kourmonen').holds_today,
            dotlan_href: 'https://evemaps.dotlan.net/system/Kourmonen',
            zkill_href: 'https://zkillboard.com/system/30003068/',
        },
    ],
    traffic: TRAFFIC,
    traffic_footnote:
        'Busiest systems by ships destroyed in September, across all 70 warzone systems. Source: zKillboard per-system API, capsules removed.',
    fronts: [
        {
            name: 'Minmatar front',
            regions: 'Heimatar and Metropolis',
            occupancy_label: '6 occupancy changes',
            ships: FRONTS.minmatar.ships,
            ships_label: FRONTS.minmatar.ships_label,
            ships_vs: FRONTS.minmatar.ships_vs,
            hottest_system: FRONTS.minmatar.hottest_system,
            dek: 'Heimatar and Metropolis. Still where most of the war is fought — Amamake led the warzone again, and the twenty-sixth is why. Six systems changed hands here. Minmatar took Eszur, Ebolfer, Hadozeko, and Ontorn. Amarr took Lantorn and Todifrauan. Klogori flipped twice and ended where it started.',
        },
        {
            name: 'Amarr front',
            regions: 'Devoid and The Bleak Lands',
            occupancy_label: '2 occupancy changes',
            ships: FRONTS.amarr.ships,
            ships_label: FRONTS.amarr.ships_label,
            ships_vs: FRONTS.amarr.ships_vs,
            hottest_system: FRONTS.amarr.hottest_system,
            dek: 'Devoid and The Bleak Lands. Kourmonen was the loudest system here, and it flipped back to Amarr on the twenty-eighth, the day after Kamela. Oyonata passed through the Angel Cartel and Minmatar and was Amarr again on the thirtieth.',
        },
    ],
    focus: {
        title: 'Amamake: 625B down',
        window_label: AMAMAKE_WINDOW,
        section_dek:
            'One story that would not fit a normal issue: the night an INIT birthday brawl in Amamake turned into a 625-billion-ISK fight at the sun.',
        cta_label: 'Read the full AAR',
        dek: [
            'INIT posted a birthday brawl for the twenty-sixth. The rumor all week was that Bombeldo was polishing an Avatar. FL33T formed Typhoons, with Apocalypses in reserve and AHBA alongside. INIT brought about 200 Abaddons. Fraternity brought Ravens, TEST brought Typhoons, and Warlock Industries formed in capitals.',
            'Warlock opened on a Nyx with the Abaddons. FL33T watched for about ten minutes, then a Devoter tackled the Nyx and Typhoons landed with a wing of Revelations. The subcaps shot INIT Apostles and reshipped as they died. The capitals stayed on the Nyx. INIT escalated into dreads. FL33T went through a month of Typhoons, then Devoters and Mallers, and still barely touched the Abaddons. Bombeldo soaked damage in a Vehement until it died, and he said on stream he was getting in a titan.',
            `The new mission was to keep that Avatar alive. It landed about 150 kilometers off the sun, while Warlock's Sarathiel sat at sun center. FL33T and INIT fought over the titan. Bombeldo doomsdayed the Apostle that warped in to repair him. FL33T landed a second Apostle, dreadbombed their Revelations onto the Sarathiel, and booshed chunks of Abaddons off the field until INIT left. He self-destructed the Avatar anyway. The last hull was Warlock's Naglfar Fleet Issue, and it took a Hel to finish it. ${AMAMAKE_SHIPS.toLocaleString('en-US')} ships were gone, and ${AMAMAKE_UNIQUE_PILOTS.toLocaleString('en-US')} pilots had been on grid.`,
        ],
        ships: AMAMAKE_SHIPS,
        isk: CAMPAIGN_ISK_DESTROYED,
        unique_pilots: AMAMAKE_UNIQUE_PILOTS,
        flip_label: '26 Sep',
        minmatar_pilots: MINMATAR_PILOTS,
        minmatar_ships: MINMATAR_DESTROYED_SHIPS,
        amarr_pilots: AMARR_PILOTS,
        amarr_ships: AMARR_DESTROYED_SHIPS,
        amarr_isk: AMARR_DESTROYED_ISK,
        minmatar_isk: MINMATAR_DESTROYED_ISK,
        other_ships: OTHER_DESTROYED_SHIPS,
        other_isk: OTHER_DESTROYED_ISK,
        engagement_mix: ENGAGEMENT_MIX,
        small_gang_kills: SMALL_GANG?.value ?? 629,
        closing: 'GFs all, until the next one.',
        links: [
            { href: AAR_URL, label: 'AAR: 625b down in Amamake' },
            { href: BATTLE_REPORT_URL, label: '26 Sep battle report' },
            { href: AMAMAKE_ZKILL, label: 'Amamake on zKillboard' },
        ],
        campaign_path: AAR_URL,
    },
    fleet: {
        tracked_fleets: 0,
        untracked_forms_lower_bound: 0,
        largest_public_pickup: 0,
        dek: 'The public formup was the 26 Sep Amamake birthday brawl, called for 22:30 EVE. Character-level boards and Discord ping internals stay off this page.',
    },
    pilots: {
        scope: 'Killmails appeared on as attacker across the warzone systems in September, from zKillboard. Solo is only one character on the killmail. Small gang, 2-10 pilots. Fleets have 25+ characters involved.',
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
        scope: 'Alliances, or corporations flying without one, ranked by killmails in the warzone. Only groups with more than half of their September kills inside the warzone are listed, so nullsec blocs passing through do not crowd out the people who live here.',
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
