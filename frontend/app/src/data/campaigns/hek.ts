/** Hek highsec campaign · metrics window 10 Nov – 30 Nov 2023. */

export const COVER_IMAGE = '/images/combatlog-cover.jpg'

/** zKill · alliance 99011978 · Hek (30002053) · 10 Nov – 30 Nov 2023 UTC. */
export const METRICS_START = '2023-11-10'
export const METRICS_END = '2023-11-30'

export const ISK_DESTROYED = 65_088_972_952
export const ISK_LOST = 81_122_603
export const KILLMAIL_COUNT = 24
export const LOSSMAIL_COUNT = 10
export const STRUCTURE_KILLMAIL_COUNT = 10
export const STRUCTURE_ISK_DESTROYED = 64_315_502_190

/** Discord announcement · 17 Nov 2023 · [SLUSH] surrender offer accepted. */
export const SURRENDER_ISK = 20_000_000_000

/** War declaration estimate · ~150B enemy structures in theater. */
export const ENEMY_STRUCTURE_VALUE_ESTIMATE = 150_000_000_000

/** Structures removed from timers after reparations · 17 Nov 2023. */
export const STRUCTURES_CLEARED_FROM_TIMERS = 13

export const CAMPAIGN_BEATS = [
    {
        date: '2023-10-23',
        label: 'Security status preparation for highsec content',
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
        label: '20B ISK surrender accepted from [SLUSH]',
        source: 'Discord · #announcements',
    },
] as const

export type CampaignKeyPerson = {
    characterId: number
    name: string
    role: string
}

export const KEY_PEOPLE: readonly CampaignKeyPerson[] = [
    { characterId: 299_286_127, name: 'Fariius', role: 'Intelligence' },
    { characterId: 2_120_834_555, name: 'Faye Vaelent', role: 'Propaganda' },
    { characterId: 2_120_647_389, name: "A'Songala", role: 'Diplomacy' },
    { characterId: 1_978_535_095, name: 'Ibn Khatab', role: 'Fleet Commander' },
    { characterId: 634_915_984, name: 'BearThatCares', role: 'Fleet Commander' },
] as const

export type CampaignHeadlineCategory = 'aar' | 'update' | 'video'

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
        url: 'https://youtu.be/DcxFeYoyTrw?si=13p0TEIybStuOQ98',
        date: '2023-11-10',
        category: 'video',
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
        url: 'https://youtu.be/N2qh4oPhWAM?si=_3Q4N4oTKC9vKWOw',
        date: '2023-11-14',
        category: 'video',
        backgroundImage: HEADLINE_BACKGROUNDS[2],
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
