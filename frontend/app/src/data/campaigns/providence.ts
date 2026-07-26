export const MONTHS = ["Jan 24", "Feb 24", "Mar 24", "Apr 24", "May 24", "Jun 24", "Jul 24", "Aug 24", "Sep 24", "Oct 24", "Nov 24", "Dec 24", "Jan 25", "Feb 25", "Mar 25"] as const

export const FLEETS_MONTHLY = [60, 44, 61, 68, 41, 38, 43, 43, 39, 48, 41, 52, 49, 71, 49]

export const CAMPAIGN_BEATS = [
    { monthIndex: 0, label: "FL33T declares war on CVA" },
    { monthIndex: 0, label: "RMC declares as CVA ally" },
    { monthIndex: 0, label: "RMC contracts AO" },
    { monthIndex: 5, label: "Providence attacks FL33T staging Fortizar" },
    { monthIndex: 8, label: "Shift to Pochven / Warzone" },
    { monthIndex: 10, label: "Return to Providence" },
    { monthIndex: 13, label: "RMC calls Imperium" },
] as const

export const ISK_DESTROYED_MONTHLY = [
309159272711, 67754022248, 94722082579, 332150073557, 45377563443, 274439879389, 366561840501, 97848990198, 25608590227, 69014515430, 68650368134, 86348846139, 123409072539, 251829053678, 130353190855
]

export const ISK_LOST_MONTHLY = [
361571122091, 81961617964, 33283151990, 180345978934, 20192479262, 217416825261, 300424230336, 64212284594, 13892408009, 47633681456, 17165292457, 41333757374, 25577325627, 199255602112, 29405844482
]

export const PERIOD_PROVIDENCE_ISK_KILLS = 2_343_227_361_634
export const PERIOD_PROVIDENCE_ISK_LOSSES = 1_633_671_601_958
export const PERIOD_CAMPAIGN_FLEETS = 747

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

/** Top FCs by fleets commanded (in-game FC role, or scheduled when untracked) · Jan 2024 – Mar 2025. */
export const TOP_FLEET_COMMANDERS: readonly FleetCommanderEntry[] = [
    { characterId: 634_915_984, name: "BearThatCares", fleetCount: 184 },
    { characterId: 2_120_307_642, name: "Casper Sullivan", fleetCount: 41 },
    { characterId: 2_114_993_571, name: "Twan Molenaar", fleetCount: 36 },
    { characterId: 148_717_474, name: "Mazer", fleetCount: 33 },
    {
        characterId: null,
        name: 'Other commanders',
        fleetCount: 117,
        isAggregate: true,
    },
]

export const OTHER_FLEET_COMMANDERS = {
    fleetCount: 117,
    commanders: [
    { characterId: 140_971_074, name: "Buppas", fleetCount: 13 },
    { characterId: 94_914_644, name: "sin Alarma", fleetCount: 13 },
    { characterId: 91_434_341, name: "Mortarian Decala", fleetCount: 11 },
    { characterId: 301_592_770, name: "Gian Bal", fleetCount: 9 },
    { characterId: 94_335_465, name: "Erik Sinulf", fleetCount: 8 },
    { characterId: 2_120_153_200, name: "Furl0w", fleetCount: 7 },
    { characterId: 1_333_721_550, name: "Inathero", fleetCount: 6 },
    { characterId: 2_115_925_566, name: "johnnieboye II", fleetCount: 5 },
    { characterId: 93_068_254, name: "Isa Kento", fleetCount: 5 },
    { characterId: 2_121_103_796, name: "Beautiful Mim", fleetCount: 5 },
    { characterId: 95_263_555, name: "Bora Makar", fleetCount: 4 },
    { characterId: 2_116_877_146, name: "Tarthir Skor", fleetCount: 4 },
    { characterId: 92_004_354, name: "Teysha Blackblade", fleetCount: 3 },
    { characterId: 1_184_744_114, name: "Ren Setion", fleetCount: 2 },
    { characterId: 93_613_873, name: "Bobb Bobbington", fleetCount: 2 },
    { characterId: 94_440_400, name: "Kyle Phat Phatumus", fleetCount: 2 },
    { characterId: 537_400_441, name: "Sevaru", fleetCount: 2 },
    { characterId: 1_771_780_065, name: "NCC 1701E", fleetCount: 2 },
    { characterId: 90_146_672, name: "Khermes", fleetCount: 2 },
    { characterId: 2_117_051_187, name: "Ronoldo Hollentco", fleetCount: 2 },
    { characterId: 2_117_683_314, name: "Teirg Askold", fleetCount: 2 },
    { characterId: 1_566_368_814, name: "Tomas Bailey", fleetCount: 2 },
    { characterId: 2_114_499_753, name: "Xadr Twitch", fleetCount: 1 },
    { characterId: 2_116_242_012, name: "Sycamoria", fleetCount: 1 },
    { characterId: 146_444_251, name: "Chronus", fleetCount: 1 },
    { characterId: 94_716_101, name: "Vengo Rin", fleetCount: 1 },
    { characterId: 2_120_834_555, name: "Faye Vaelent", fleetCount: 1 },
    { characterId: 93_672_441, name: "Orion Sa-Solo", fleetCount: 1 },
    ],
} as const

/** Top pilots by player · distinct fleet instances across alts · excludes TOP_FLEET_COMMANDERS · Jan 2024 – Mar 2025. */
export const TOP_FLEET_PILOTS = [
    { characterId: 2_121_103_796, name: "Beautiful Mim", fleetCount: 276 },
    { characterId: 1_444_365_537, name: "Tasha Bailey", fleetCount: 214 },
    { characterId: 187_187_113, name: "Lioane", fleetCount: 209 },
    { characterId: 345_180_234, name: "XVSSBR", fleetCount: 206 },
    { characterId: 1_685_650_958, name: "Elador", fleetCount: 196 },
] as const

export const FLEET_PILOTS = 321
export const FLEET_CHARACTERS = 598
export const FLEET_PARTICIPATION_PCT = 99

export const GROSS_ISK_KILLS = PERIOD_PROVIDENCE_ISK_KILLS
export const GROSS_ISK_LOSSES = PERIOD_PROVIDENCE_ISK_LOSSES
export const CAMPAIGN_ISK_DESTROYED = GROSS_ISK_KILLS

export const COVER_IMAGE = '/images/providence-campaign.webp'

export type CampaignHeadlineCategory = 'aar' | 'industry'

export const HEADLINE_AAR_BACKGROUNDS = ["/images/combatlog-tile-background.webp", "/images/dread-card.jpg"] as const

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

/** u/BearThatCares · r/Eve Providence campaign AARs · Jan 2024 – Mar 2025. */
export const HEADLINES: readonly CampaignHeadline[] = [
    {
        title: "FL33T DECLARES WAR ON CVA",
        url: "https://www.reddit.com/r/Eve/comments/190grzs/fl33t_celebrates_1_year_and_declares_war_on_cva/",
        date: "2024-01-07",
        category: "aar",
        backgroundImage: HEADLINE_AAR_BACKGROUNDS[0],
        upvotes: 0,
        comments: 0,
        views: "—",
    },
    {
        title: "20 DAYS IN PROVIDENCE",
        url: "https://www.reddit.com/r/Eve/comments/19bcsz7/20_days_in_providence/",
        date: "2024-01-20",
        category: "aar",
        backgroundImage: HEADLINE_AAR_BACKGROUNDS[1],
        upvotes: 0,
        comments: 0,
        views: "—",
    },
    {
        title: "ABSOLUTE ORDER BAITED ON A FREE RAITARU",
        url: "https://www.reddit.com/r/Eve/comments/1e332ss/aar_absolute_order_baited_on_a_free_raitaru/",
        date: "2024-07-16",
        category: "aar",
        backgroundImage: HEADLINE_AAR_BACKGROUNDS[0],
        upvotes: 0,
        comments: 0,
        views: "—",
    },
    {
        title: "400B DOWN IN PROVIDENCE",
        url: "https://www.reddit.com/r/Eve/comments/1e8qqve/aar_400b_down_in_providence_no_moon_drills_in/",
        date: "2024-07-21",
        category: "aar",
        backgroundImage: HEADLINE_AAR_BACKGROUNDS[1],
        upvotes: 0,
        comments: 0,
        views: "—",
    },
    {
        title: "MINMIL BITES OFF MORE THAN THEY CAN CHEW",
        url: "https://www.reddit.com/r/Eve/comments/1g8pcse/aar_minmil_bites_off_more_than_they_can_chew/",
        date: "2024-10-21",
        category: "aar",
        backgroundImage: HEADLINE_AAR_BACKGROUNDS[0],
        upvotes: 0,
        comments: 0,
        views: "—",
    },
    {
        title: "FL33T VS PROVIDENCE",
        url: "https://www.reddit.com/r/Eve/comments/1g2xq0k/aar_fl33t_vs_providence/",
        date: "2024-10-06",
        category: "aar",
        backgroundImage: HEADLINE_AAR_BACKGROUNDS[1],
        upvotes: 0,
        comments: 0,
        views: "—",
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
