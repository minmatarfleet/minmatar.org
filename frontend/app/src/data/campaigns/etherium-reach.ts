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
    { monthIndex: 3, label: 'SL0W collapse' },
    { monthIndex: 5, label: 'B0SS losing ground' },
    { monthIndex: 6, label: 'RMC wins war' },
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

export const FLEET_PILOTS = 269
export const FLEET_CHARACTERS = 535
export const FLEET_PARTICIPATION_PCT = 79

export const GROSS_ISK_KILLS = 1_051_116_941_129
export const GROSS_ISK_LOSSES = 682_445_654_452

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

export const OPSEC_PRIVATE_LINE_ITEM = 375_000_000_000
export const GROSS_CORP_ALL = GROSS_CORP_TAX_TOTAL + OPSEC_PRIVATE_LINE_ITEM

export const DRONELANDS_REGIONS = [
    'Etherium Reach',
    'The Kalevala Expanse',
    'The Spire',
    'Perrigen Falls',
] as const

export const ISK_KILLS_BY_REGION: Record<string, number> = {
    'Etherium Reach': 272_473_438_105,
    'The Kalevala Expanse': 567_846_664_375,
    'The Spire': 119_501_683_344,
    'Perrigen Falls': 91_295_155_305,
}

export const ISK_LOSSES_BY_REGION: Record<string, number> = {
    'Etherium Reach': 319_141_222_701,
    'The Kalevala Expanse': 223_026_141_112,
    'The Spire': 123_562_845_349,
    'Perrigen Falls': 16_715_445_290,
}

export const DRONELANDS_REGIONS_BY_DESTROYED = [...DRONELANDS_REGIONS].sort(
    (a, b) => ISK_KILLS_BY_REGION[b] - ISK_KILLS_BY_REGION[a],
)

export const COVER_IMAGE = '/images/etherium-card.jpg'

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
