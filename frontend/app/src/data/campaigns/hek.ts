/** Hek / Metropolis highsec campaign · metrics window 10 Nov – 30 Nov 2023. */

export const COVER_IMAGE = '/images/combatlog-cover.jpg'

/** zKill · alliance 99011978 · Metropolis region 10000042 · 10 Nov – 30 Nov 2023 UTC. */
export const METRICS_START = '2023-11-10'
export const METRICS_END = '2023-11-30'

export const ISK_DESTROYED = 232_474_264_895
export const ISK_LOST = 50_221_325_563
export const KILLMAIL_COUNT = 1_963
export const LOSSMAIL_COUNT = 882

/** Discord announcement · 17 Nov 2023 · [SLUSH] surrender offer accepted. */
export const HMA_REPARATIONS_ISK = 20_000_000_000

/** War declaration estimate · ~150B enemy structures in theater. */
export const ENEMY_STRUCTURE_VALUE_ESTIMATE = 150_000_000_000

/** Structures removed from timers after reparations · 17 Nov 2023. */
export const STRUCTURES_CLEARED_FROM_TIMERS = 13

export const CAMPAIGN_BEATS = [
    {
        date: '2023-10-23',
        label: 'Security status prep for Metropolis content',
        source: 'Discord · #archive-announcements',
    },
    {
        date: '2023-11-10',
        label: 'War declared on Hek Mining Association',
        source: 'Discord · #announcements',
    },
    {
        date: '2023-11-14',
        label: 'Corruption manifesto published on Reddit',
        source: 'r/Eve · BearThatCares',
    },
    {
        date: '2023-11-17',
        label: '20B ISK HMA reparations accepted from [SLUSH]',
        source: 'Discord · #announcements',
    },
    {
        date: '2023-11-18',
        label: 'Dual-theater day — structure pressure in Hek and caps in Floseswin',
        source: 'Rat Chronicle · r/Eve',
    },
    {
        date: '2023-11-19',
        label: 'Ore buyback program announced for freed systems',
        source: 'Discord · #archive-announcements',
    },
] as const

export const REMAINING_TARGETS = [
    'Nebula Market & Industry (Azbel)',
    'HMA Presents — Rogue One (Raitaru)',
    "Rogue's Gallery (Athanor)",
    'Nebula Mining Operations (Athanor)',
] as const

export type CampaignHeadlineCategory = 'aar' | 'update'

export const HEADLINE_BACKGROUNDS = [
    '/images/combatlog-tile-background.webp',
    '/images/warzone-card.jpg',
    '/images/advocate-card.jpg',
] as const

export type CampaignHeadline = {
    title: string
    url: string
    date: string
    category: CampaignHeadlineCategory
    backgroundImage: string
}

export const HEADLINES: readonly CampaignHeadline[] = [
    {
        title: 'FL33T declares war on highsec cartels',
        url: 'https://www.reddit.com/r/Eve/comments/17s47re/fl33t_declares_war_on_highsec_cartels/',
        date: '2023-11-10',
        category: 'update',
        backgroundImage: HEADLINE_BACKGROUNDS[1],
    },
    {
        title: 'The end to corruption in Minmatar high security space',
        url: 'https://www.reddit.com/r/Eve/comments/17v814t/the_end_to_corruption_in_minmatar_high_security/',
        date: '2023-11-14',
        category: 'aar',
        backgroundImage: HEADLINE_BACKGROUNDS[0],
    },
    {
        title: 'Hek is... free?',
        url: 'https://www.reddit.com/r/Eve/comments/17v81hp/hek_is_free/',
        date: '2023-11-14',
        category: 'update',
        backgroundImage: HEADLINE_BACKGROUNDS[2],
    },
    {
        title: 'Capital Ships Down in Floseswin',
        url: 'https://www.reddit.com/r/Eve/comments/17yhqk1/capital_ships_down_in_floseswin/',
        date: '2023-11-18',
        category: 'aar',
        backgroundImage: HEADLINE_BACKGROUNDS[0],
    },
] as const

export function formatIsk(isk: number): string {
    if (isk >= 1_000_000_000_000) {
        return `${(isk / 1_000_000_000_000).toFixed(2)}T`
    }
    if (isk >= 1_000_000_000) {
        return `${(isk / 1_000_000_000).toFixed(1)}B`
    }
    if (isk >= 1_000_000) {
        return `${(isk / 1_000_000).toFixed(0)}M`
    }
    return `${(isk / 1_000).toFixed(0)}K`
}

export type CampaignRowTone = 'info' | 'success' | 'warning' | 'danger' | undefined

export type CampaignTableRow = {
    cells: [string, string] | [string, string, string]
    tone?: CampaignRowTone
}
