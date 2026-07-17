export const MONTHS = [
    'Nov 25',
    'Dec 25',
    'Jan 26',
    'Feb 26',
    'Mar 26',
    'Apr 26',
    'May 26',
    'Jun 26',
] as const

export const MINING_GROSS_ISK = [
    1_162_507_791,
    20_615_553_924,
    34_746_106_656,
    56_922_116_337,
    47_492_128_266,
    22_976_608_887,
    14_032_926_563,
    5_181_205_669,
]

export const RATTING_GROSS_ISK = [
    0,
    0,
    514_094_888,
    10_871_441_441,
    25_170_936_481,
    17_948_820_690,
    10_023_084_431,
    4_328_512_446,
]

export const PI_GROSS_ISK = [
    0,
    0,
    4_343_456_011,
    12_696_392_515,
    66_975_266_805,
    57_399_926_339,
    53_482_436_997,
    33_673_092_674,
]

/** Est. · 750M/day at release (5 Jan 2026) · ~10% monthly decline. */
export const EXPLORATION_GROSS_ISK = [
    0,
    0,
    20_250_000_000,
    18_900_000_000,
    18_832_500_000,
    16_402_500_000,
    15_254_325_000,
    7_971_615_000,
]

export const FLEETS_MONTHLY = [20, 7, 17, 28, 21, 12, 9, 8]

export const CAMPAIGN_BEATS = [
    { monthIndex: 3, label: 'SL0W collapses' },
    { monthIndex: 5, label: 'B0SS loses region' },
    { monthIndex: 6, label: 'RMC consolidates space' },
    { monthIndex: 7, label: 'TRD disbands' },
] as const

export const PERIOD_DRONELANDS_ISK_KILLS = 3_487_300_958_894
export const PERIOD_DRONELANDS_ISK_LOSSES = 921_347_487_752
export const PERIOD_OUTSIDE_ISK_KILLS = 9_003_539_041_106
export const PERIOD_OUTSIDE_ISK_LOSSES = 2_529_722_512_248

export const ISK_DESTROYED_MONTHLY = [
    345_813_414_159,
    478_398_512_311,
    925_261_244_915,
    691_585_269_663,
    638_610_082_208,
    265_190_928_437,
    87_446_288_666,
    54_995_218_535,
]

export const PERIOD_OUTSIDE_FLEETS = 149
export const PERIOD_DRONELANDS_FLEETS = 122

export type FleetCommanderEntry =
    | {
          characterId: number
          name: string
          fleetCount: number
      }
    | {
          characterId: null
          name: string
          fleetCount: number
          isAggregate: true
      }

/** Top FCs by EveFleetInstance count · Etherium Reach · Nov 2025 – Jun 18 2026. */
export const TOP_FLEET_COMMANDERS: readonly FleetCommanderEntry[] = [
    { characterId: 634_915_984, name: 'BearThatCares', fleetCount: 46 },
    { characterId: 2_120_307_642, name: 'Casper Sullivan', fleetCount: 21 },
    { characterId: 1_907_307_618, name: 'Chad VanGaalen', fleetCount: 16 },
    { characterId: 2_118_080_229, name: 'Vex Drake', fleetCount: 13 },
    {
        characterId: null,
        name: 'Other commanders',
        fleetCount: 26,
        isAggregate: true,
    },
]

/** Remaining FCs · rank 5+ · Nov 2025 – Jun 18 2026 · 5 instances have no assigned FC. */
export const OTHER_FLEET_COMMANDERS = {
    fleetCount: 26,
    commanders: [
        { characterId: 90_146_672, name: 'Khermes', fleetCount: 3 },
        { characterId: 93_068_254, name: 'Isa Kento', fleetCount: 3 },
        { characterId: 93_672_441, name: 'Orion Sa-Solo', fleetCount: 2 },
        { characterId: 2_117_051_187, name: 'Ronoldo Hollentco', fleetCount: 2 },
        { characterId: 856_157_051, name: 'Angskel Issod', fleetCount: 2 },
        { characterId: 2_117_059_479, name: 'MiniSpartan', fleetCount: 2 },
        { characterId: 454_273_965, name: 'Rafaella Carra', fleetCount: 1 },
        { characterId: 955_656_982, name: 'Tyshalle Fallen', fleetCount: 1 },
        { characterId: 2_116_242_012, name: 'Sycamoria', fleetCount: 1 },
        { characterId: 1_771_780_065, name: 'NCC 1701E', fleetCount: 1 },
        { characterId: 154_198_067, name: 'Barret Smythe', fleetCount: 1 },
        { characterId: 95_115_998, name: 'Alexander Akachii', fleetCount: 1 },
        { characterId: 2_122_947_599, name: 'Jozas Djevojka', fleetCount: 1 },
    ],
} as const

/** Top pilots by player · distinct fleet instances across alts · excludes TOP_FLEET_COMMANDERS · Nov 2025 – Jun 2026. */
export const TOP_FLEET_PILOTS = [
    { characterId: 187_187_113, name: 'Lioane', fleetCount: 62 },
    { characterId: 762_475_669, name: 'SADIST666', fleetCount: 59 },
    { characterId: 1_444_365_537, name: 'Tasha Bailey', fleetCount: 52 },
    { characterId: 92_361_974, name: 'Dima Volenkov', fleetCount: 46 },
    { characterId: 2_121_103_796, name: 'Beautiful Mim', fleetCount: 43 },
] as const

export type TopKrabberEntry = {
    characterId: number
    name: string
    totalIsk: number
    miningIsk?: number
    rattingIsk?: number
    piIsk?: number
}

/** Top pilots by player · mining + PI + ratting in dronelands · Nov 2025 – Jun 2026. */
export const TOP_KRABBERS: readonly TopKrabberEntry[] = [
    {
        characterId: 91_439_324,
        name: 'Keldor Eternia',
        totalIsk: 65_184_679_264,
        miningIsk: 52_415_541_583,
        piIsk: 12_725_904_800,
        rattingIsk: 43_232_881,
    },
    {
        characterId: 2_121_855_073,
        name: 'Bliink Nado',
        totalIsk: 38_739_211_246,
        miningIsk: 35_765_584_846,
        piIsk: 2_973_626_400,
        rattingIsk: 0,
    },
    {
        characterId: 2_124_070_255,
        name: 'Maurdakar',
        totalIsk: 18_101_364_435,
        miningIsk: 15_250_637_133,
        piIsk: 2_751_863_600,
        rattingIsk: 98_863_702,
    },
    {
        characterId: 2_124_076_088,
        name: 'DudeBroMan',
        totalIsk: 18_094_581_179,
        miningIsk: 0,
        piIsk: 18_094_581_179,
        rattingIsk: 0,
    },
    {
        characterId: 2_123_699_290,
        name: 'Lilith Himmelsgaenger',
        totalIsk: 16_868_910_139,
        miningIsk: 0,
        piIsk: 14_954_831_316,
        rattingIsk: 1_914_078_823,
    },
] as const

export const FLEET_PILOTS = 269
export const FLEET_CHARACTERS = 535
export const FLEET_PARTICIPATION_PCT = 79

export const GROSS_ISK_KILLS = PERIOD_DRONELANDS_ISK_KILLS
export const GROSS_ISK_LOSSES = PERIOD_DRONELANDS_ISK_LOSSES

/** Courier rewards · finished contracts · start or end in dronelands. */
export const GROSS_PLAYER_COURIER_REWARDS = 35_827_818_505
/** Fleet industry orders · delivered target margin · R-6KYM, Etherium Reach. */
export const GROSS_PLAYER_INDUSTRY_PROFIT = 50_623_137_380

export const GROSS_PLAYER_MINING = 203_129_154_092
export const GROSS_PLAYER_RATTING = 68_856_890_377
/** Export tax only — import counted under alliance income. */
export const GROSS_PLAYER_PI = 228_570_571_341

export const GROSS_PLAYER_EXPLORATION = EXPLORATION_GROSS_ISK.reduce(
    (sum, value) => sum + value,
    0,
)

export const GROSS_PLAYER_TRACKED =
    GROSS_PLAYER_MINING +
    GROSS_PLAYER_RATTING +
    GROSS_PLAYER_PI +
    GROSS_PLAYER_COURIER_REWARDS +
    GROSS_PLAYER_INDUSTRY_PROFIT

export const GROSS_PLAYER_TOTAL = GROSS_PLAYER_TRACKED + GROSS_PLAYER_EXPLORATION

export const GROSS_CORP_RATTING_TAX = 6_525_260_429
export const GROSS_CORP_PI_TAX = 2_708_202_161
/** Positive industry_job_tax · corp wallet journal · Jan 2026+. */
export const GROSS_CORP_INDUSTRY_TAX = 4_533_779_479
/** Positive brokers_fee · corp wallet journal · Jan 2026+. */
export const GROSS_CORP_BROKER_FEES = 2_658_339_944

export const GROSS_CORP_TAX_TOTAL =
    GROSS_CORP_RATTING_TAX +
    GROSS_CORP_PI_TAX +
    GROSS_CORP_INDUSTRY_TAX +
    GROSS_CORP_BROKER_FEES

/** Metenox moon income · opsec. */
export const OPSEC_MOON_INCOME = 406_250_000_000
/** Alliance diplomatic contract margin. */
export const OPSEC_CONTRACT_INCOME = 100_000_000_000
/** Jul 2026 wind-down announcement · moons and contracts. */
export const GROSS_ALLIANCE_MOONS_AND_CONTRACTS =
    OPSEC_MOON_INCOME + OPSEC_CONTRACT_INCOME
export const GROSS_CORP_ALL =
    GROSS_CORP_TAX_TOTAL + GROSS_ALLIANCE_MOONS_AND_CONTRACTS

/** Jul 2026 wind-down announcement headline figures. */
export const CAMPAIGN_ISK_DESTROYED = ISK_DESTROYED_MONTHLY.reduce(
    (sum, value) => sum + value,
    0,
)
export const CAMPAIGN_PILOT_INCOME = GROSS_PLAYER_TOTAL
/** Pilot income plus alliance disclosed income · ~1.2T ISK. */
export const CAMPAIGN_TOTAL_INCOME = CAMPAIGN_PILOT_INCOME + GROSS_CORP_ALL

export const DRONELANDS_REGIONS = [
    'Etherium Reach',
    'The Kalevala Expanse',
    'The Spire',
    'Perrigen Falls',
] as const

/** zKill Nov 25 – Jun 26 × monthly DB regional share within dronelands. */
export const ISK_KILLS_BY_REGION: Record<string, number> = {
    'Etherium Reach': 1_177_496_423_540,
    'The Kalevala Expanse': 1_742_238_881_766,
    'The Spire': 522_908_504_868,
    'Perrigen Falls': 44_657_148_720,
}

export const ISK_LOSSES_BY_REGION: Record<string, number> = {
    'Etherium Reach': 409_194_497_173,
    'The Kalevala Expanse': 351_203_192_606,
    'The Spire': 156_025_867_616,
    'Perrigen Falls': 4_923_930_357,
}

export const DRONELANDS_REGIONS_BY_DESTROYED = [...DRONELANDS_REGIONS].sort(
    (a, b) => ISK_KILLS_BY_REGION[b] - ISK_KILLS_BY_REGION[a],
)

export const COVER_IMAGE = '/images/etherium-campaign.webp'

export type CampaignHeadlineCategory = 'aar' | 'industry'

export const HEADLINE_AAR_BACKGROUNDS = [
    '/images/combatlog-tile-background.webp',
    '/images/dread-card.jpg',
] as const

export const HEADLINE_INDUSTRY_BACKGROUND = '/images/industry-card.jpg'

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

/** u/BearThatCares · r/Eve campaign AARs and updates · Jan–Mar 2026. */
export const HEADLINES: readonly CampaignHeadline[] = [
    {
        title: '300B DREAD BRAWL IN DRONELANDS',
        url: 'https://www.reddit.com/r/Eve/comments/1q7jarz/aar_dronelands_dreads_destruction_300b_dread_brawl/',
        date: '2026-01-08',
        category: 'aar',
        backgroundImage: HEADLINE_AAR_BACKGROUNDS[0],
        upvotes: 128,
        comments: 81,
        views: '36K',
    },
    {
        title: '200B DREAD BRAWL IN DRONELANDS',
        url: 'https://www.reddit.com/r/Eve/comments/1r3qwgt/aar_200b_dread_brawl_in_dronelands/',
        date: '2026-02-13',
        category: 'aar',
        backgroundImage: HEADLINE_AAR_BACKGROUNDS[1],
        upvotes: 91,
        comments: 27,
        views: '27K',
    },
    {
        title: 'How Minmatar Fleet visualizes our industrial supply chain with ESI',
        url: 'https://www.reddit.com/r/Eve/comments/1r8o0da/how_minmatar_fleet_visualizes_our_industrial/',
        date: '2026-02-19',
        category: 'industry',
        backgroundImage: HEADLINE_INDUSTRY_BACKGROUND,
        upvotes: 132,
        comments: 25,
        views: '25K',
    },
    {
        title: 'We caught our first supercarrier',
        url: 'https://www.reddit.com/r/Eve/comments/1rmw8if/aar_we_caught_our_first_supercarrier/',
        date: '2026-03-07',
        category: 'aar',
        backgroundImage: HEADLINE_AAR_BACKGROUNDS[0],
        upvotes: 85,
        comments: 25,
        views: '23K',
    },
    {
        title: '1.3T+ DREAD BRAWL IN DRONELANDS',
        url: 'https://www.reddit.com/r/Eve/comments/1rsdgg9/aar_13t_dread_brawl_in_dronelands/',
        date: '2026-03-13',
        category: 'aar',
        backgroundImage: HEADLINE_AAR_BACKGROUNDS[1],
        upvotes: 135,
        comments: 85,
        views: '33K',
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
