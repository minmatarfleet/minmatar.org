export const MONTHS = ['Feb 24', 'Mar 24', 'Apr 24', 'May 24'] as const

/** zKill · FL33T kills in Scalding Pass · Feb 1 – May 27 2024. */
export const ISK_DESTROYED_MONTHLY = [
    8_622_363_898,
    169_228_329,
    318_228_887_641,
    41_440_496_548,
] as const

export const FLEETS_MONTHLY = [1, 0, 20, 5] as const

export const CAMPAIGN_BEATS = [
    { monthIndex: 0, label: 'Strategic target named' },
    { monthIndex: 2, label: 'Capital fight in F-5FDA' },
    { monthIndex: 3, label: 'Campaign wind-down' },
] as const

/** zKill · alliance kills in Scalding Pass region · Feb–May 2024. */
export const PERIOD_SCALDING_ISK_KILLS = 368_460_976_887
export const PERIOD_SCALDING_ISK_LOSSES = 40_650_648_098
export const PERIOD_SCALDING_FLEETS = 26

export const CONTRACTED_ISK = 25_000_000_000

export const CONSTELLATIONS_BY_DESTROYED = [
    '4YFT-F',
    'QI1M-Q',
    'ENP-SH',
    'P-I9PF',
    'CN5-F2',
    '51ZT-6',
    'YCM-AI',
] as const

export const ISK_DESTROYED_BY_CONSTELLATION: Record<string, number> = {
    '4YFT-F': 296_980_144_249,
    'QI1M-Q': 39_092_218_166,
    'ENP-SH': 12_744_428_368,
    'P-I9PF': 12_331_160_517,
    'CN5-F2': 5_772_220_504,
    '51ZT-6': 1_102_970_739,
    'YCM-AI': 437_833_873,
}

export type FleetCommanderEntry = {
    characterId: number
    name: string
    fleetCount: number
}

/** Top FCs · Scalding Pass fleet instances · Feb–May 2024. */
export const TOP_FLEET_COMMANDERS: readonly FleetCommanderEntry[] = [
    { characterId: 634_915_984, name: 'BearThatCares', fleetCount: 15 },
    { characterId: 1_978_535_095, name: 'Ibn Khatab', fleetCount: 7 },
    { characterId: 2_114_993_571, name: 'Twan Molenaar', fleetCount: 3 },
    { characterId: 2_120_307_642, name: 'Casper Sullivan', fleetCount: 1 },
] as const

/** Top pilots · distinct Scalding Pass fleet instances · Feb–May 2024. */
export const TOP_FLEET_PILOTS = [
    { characterId: 1_444_365_537, name: 'Tasha Bailey', fleetCount: 23 },
    { characterId: 345_180_234, name: 'XVSSBR', fleetCount: 22 },
    { characterId: 480_522_219, name: 'Theo Antillis', fleetCount: 22 },
    { characterId: 1_978_535_095, name: 'Ibn Khatab', fleetCount: 20 },
    { characterId: 94_329_280, name: 'Ninereid Deninard', fleetCount: 19 },
] as const

export const COVER_IMAGE = '/images/scalding-campaign.webp'

export type CampaignHeadlineCategory = 'aar'

export type CampaignHeadline = {
    title: string
    url: string
    date: string
    category: CampaignHeadlineCategory
    backgroundImage: string
    upvotes: number
    comments: number
    views: string | number
}

/** u/BearThatCares · r/Eve · Apr 2024 capital engagement. */
export const HEADLINES: readonly CampaignHeadline[] = [
    {
        title: '5 HOUR ENGAGEMENT IN SCALDING PASS & CAPITAL FIGHT',
        url: 'https://www.reddit.com/r/Eve/comments/1bwpyeo/aar_5_hour_engagement_in_scalding_pass_capital/',
        date: '2024-04-05',
        category: 'aar',
        backgroundImage: '/images/combatlog-tile-background.webp',
        upvotes: 138,
        comments: 30,
        views: '—',
    },
] as const

export function toBillions(isk: number): number {
    return Math.round((isk / 1_000_000_000) * 100) / 100
}

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
