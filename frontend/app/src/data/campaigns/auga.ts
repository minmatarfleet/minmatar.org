/** Auga system siege · 12–18 Jul YC128 UTC · zKill + Discord + alliance fleets */

export const COVER_IMAGE = '/images/home-auga-cover.jpg'

/** New Eden calendar year (Gregorian − 1898). Distinguishes this siege from other Auga pushes. */
export const YC_YEAR = 128
export const YC_LABEL = `YC${YC_YEAR}` as const
/** URL slug — includes YC so future Auga sieges can coexist. */
export const SLUG = `auga-yc${YC_YEAR}` as const
export const CANONICAL_PATH = `/campaigns/${SLUG}/` as const
export const ALLIANCE_PATH = `/alliance/campaigns/${SLUG}/` as const

export const SOLAR_SYSTEM_ID = 30_002_542
export const ZKILL_SYSTEM_URL = `https://zkillboard.com/system/${SOLAR_SYSTEM_ID}/`

export const METRICS_START = '2026-07-12'
export const METRICS_END = '2026-07-18'

export function toYcYear(gregorianYear: number): number {
    return gregorianYear - 1898
}

export function formatYcDate(isoDate: string): string {
    const date = new Date(`${isoDate}T00:00:00Z`)
    const day = date.toLocaleDateString('en-GB', { day: 'numeric', timeZone: 'UTC' })
    const month = date.toLocaleDateString('en-GB', { month: 'short', timeZone: 'UTC' })
    return `${day} ${month} YC${toYcYear(date.getUTCFullYear())}`
}

/** Ship kills only (capsules excluded). */
export const SHIPS_DESTROYED = 1_581
export const PODS = 310
export const KILLMAILS_INCL_PODS = 1_891
export const CAMPAIGN_ISK_DESTROYED = 95_630_000_000
export const UNIQUE_PILOTS = 1_177

export const MINMATAR_PILOTS = 370
export const AMARR_PILOTS = 343
export const ANGEL_PILOTS = 114

export const MINMATAR_DESTROYED_SHIPS = 705
export const MINMATAR_DESTROYED_ISK = 43_140_000_000
export const AMARR_DESTROYED_SHIPS = 657
export const AMARR_DESTROYED_ISK = 35_280_000_000
/** Residual so Min + Amarr + Other = campaign totals */
export const OTHER_DESTROYED_SHIPS = 219
export const OTHER_DESTROYED_ISK = 17_210_000_000

export const DAYS = ['Jul 12', 'Jul 13', 'Jul 14', 'Jul 15', 'Jul 16', 'Jul 17', 'Jul 18'] as const

export const SHIPS_DESTROYED_DAILY = [225, 178, 268, 208, 135, 404, 163] as const

export const ENGAGEMENT_MIX = [
    { label: 'Small gang (2–10)', value: 869 },
    { label: 'Solo', value: 486 },
    { label: 'Fleet (11+)', value: 226 },
] as const

export type FleetCommanderEntry = {
    characterId: number
    name: string
    note: string
}

export const FLEET_COMMANDERS: readonly FleetCommanderEntry[] = [
    {
        characterId: 90_146_672,
        name: 'Khermes',
        note: 'Opened the July 12th push with propaganda beacons, pulling over 143 pilots across several hours.',
    },
    {
        characterId: 2_117_059_479,
        name: 'MiniSpartan',
        note: 'Ran three fleets through the siege, keeping firm pressure on Auga and the wider militia push.',
    },
    {
        characterId: 2_114_993_571,
        name: 'Twan Molenaar',
        note: 'Drove the campaign across AUTZ and EUTZ, flipping the system on the morning of July 18th.',
    },
    {
        characterId: 634_915_984,
        name: 'BearThatCares',
        note: 'Kept USTZ overnight handoffs from Twan and MiniSpartan rolling, with a 171-pilot Auga pickup.',
    },
    {
        characterId: 2_120_307_642,
        name: 'Casper Sullivan',
        note: 'Took fleet boss twice on handoffs, supplied outposts and propaganda beacons, and drove advantage.',
    },
    {
        characterId: 1_173_806_786,
        name: 'Annah Kitheran',
        note: 'Militia FC on battlefields and downtime objectives, trading fleet boss shifts with Twan Molenaar.',
    },
    {
        characterId: 2_118_645_041,
        name: 'Kiki Of Merri',
        note: 'Squad commander on Auga push fleets who covered critical handoffs on July 12th, 14th, and 18th.',
    },
    {
        characterId: 537_400_441,
        name: 'Sevaru',
        note: 'Stood up a Torpedo Typhoon fleet that kept the Auga push flowing straight through the campaign.',
    },
] as const

export type NotableEvent = {
    when: string
    kills: number | null
    isk: number | null
    pilots: number | null
    note: string
    url: string
}

export const NOTABLE_EVENTS: readonly NotableEvent[] = [
    {
        when: 'Jul 12 17:32',
        kills: 16,
        isk: 3_150_000_000,
        pilots: 56,
        note: 'Propaganda beacons are deployed. Opening brawl.',
        url: 'https://br.evetools.org/related/30002542/202607121732',
    },
    {
        when: 'Jul 12 18:34',
        kills: 27,
        isk: 6_090_000_000,
        pilots: 103,
        note: 'Khermes fleet meets Amarr response.',
        url: 'https://br.evetools.org/related/30002542/202607121834',
    },
    {
        when: 'Jul 14 18:00',
        kills: 45,
        isk: 16_710_000_000,
        pilots: null,
        note: 'EUTZ Round 1 against Amarr in Auga.',
        url: 'https://br.evetools.org/related/30002542/202607141800',
    },
    {
        when: 'Jul 15 01:44',
        kills: 35,
        isk: 3_130_000_000,
        pilots: 68,
        note: 'Overnight fleet brawl, heavy Minmatar losses.',
        url: 'https://br.evetools.org/related/30002542/202607150144',
    },
    {
        when: 'Jul 15 20:14',
        kills: 1,
        isk: 4_680_000_000,
        pilots: 31,
        note: 'Amarr lose a Revelation — single largest killmail of the siege.',
        url: 'https://zkillboard.com/kill/137030626/',
    },
    {
        when: 'Jul 15 21:45',
        kills: 24,
        isk: 2_330_000_000,
        pilots: 73,
        note: 'Annah takes over EUTZ fleet and evenly trades.',
        url: 'https://br.evetools.org/related/30002542/202607152145',
    },
    {
        when: 'Jul 17 17:43–19:08',
        kills: 47,
        isk: 5_300_000_000,
        pilots: 80,
        note: 'Peak day. Armor cruiser rounds 2–3 in militia comms.',
        url: 'https://br.evetools.org/related/30002542/202607171743',
    },
    {
        when: 'Jul 18 09:19',
        kills: null,
        isk: null,
        pilots: null,
        note: 'Twan: “Auga flip incoming” — siege objective call',
        url: ZKILL_SYSTEM_URL,
    },
] as const

export type PilotKillCount = {
    characterId: number
    name: string
    killmails: number
}

/** Top Minmatar militia on Auga ship kills (excl. blank-portrait WCXX bots). */
export const MILITIA_TOP: readonly PilotKillCount[] = [
    { characterId: 2_114_993_571, name: 'Twan Molenaar', killmails: 94 },
    { characterId: 1_173_806_786, name: 'Annah Kitheran', killmails: 73 },
    { characterId: 1_444_365_537, name: 'Tasha Bailey', killmails: 58 },
    { characterId: 2_112_149_192, name: 'Kong iBUN', killmails: 56 },
    { characterId: 2_117_059_479, name: 'MiniSpartan', killmails: 53 },
    { characterId: 2_121_887_372, name: 'Donald Barr', killmails: 51 },
    { characterId: 191_010_741, name: 'Ninlarra', killmails: 46 },
    { characterId: 1_564_908_281, name: 'cursedlion', killmails: 46 },
    { characterId: 889_117_590, name: 'Snake Bliskan', killmails: 42 },
    { characterId: 90_255_812, name: 'Rock Vogel', killmails: 42 },
    { characterId: 2_122_422_795, name: 'Number 95', killmails: 41 },
    { characterId: 2_118_645_041, name: 'Kiki Of Merri', killmails: 40 },
    { characterId: 95_277_360, name: 'Enderas Tsero', killmails: 38 },
    { characterId: 2_118_274_002, name: 'Aith of Merri', killmails: 37 },
    { characterId: 1_858_474_200, name: 'KingSaphira', killmails: 36 },
]

/** Overall leaderboard shown as the portrait table. */
export const MILITIA_TOP_5: readonly PilotKillCount[] = MILITIA_TOP.slice(0, 5)

export const MILITIA_SOLO: readonly PilotKillCount[] = [
    { characterId: 1_564_908_281, name: 'cursedlion', killmails: 27 },
    { characterId: 92_532_405, name: 'Mr Ownage Acami', killmails: 17 },
    { characterId: 90_204_495, name: 'PlutoniuM86', killmails: 14 },
    { characterId: 874_614_389, name: 'Maria Fernandez', killmails: 13 },
    { characterId: 191_010_741, name: 'Ninlarra', killmails: 9 },
    { characterId: 2_114_993_571, name: 'Twan Molenaar', killmails: 7 },
    { characterId: 91_359_918, name: 'Kleen Enkook', killmails: 7 },
    { characterId: 90_301_943, name: 'Felicia Nethers', killmails: 6 },
    { characterId: 1_635_090_924, name: 'R15', killmails: 6 },
    { characterId: 490_956_277, name: 'Major Theef', killmails: 5 },
]

export const MILITIA_GANG: readonly PilotKillCount[] = [
    { characterId: 2_121_887_372, name: 'Donald Barr', killmails: 40 },
    { characterId: 1_173_806_786, name: 'Annah Kitheran', killmails: 38 },
    { characterId: 2_114_993_571, name: 'Twan Molenaar', killmails: 37 },
    { characterId: 2_112_149_192, name: 'Kong iBUN', killmails: 31 },
    { characterId: 2_122_422_795, name: 'Number 95', killmails: 27 },
    { characterId: 191_010_741, name: 'Ninlarra', killmails: 27 },
    { characterId: 95_277_360, name: 'Enderas Tsero', killmails: 27 },
    { characterId: 1_761_145_024, name: 'Dato Koppla', killmails: 25 },
    { characterId: 889_117_590, name: 'Snake Bliskan', killmails: 25 },
    { characterId: 2_117_059_479, name: 'MiniSpartan', killmails: 25 },
]

export const MILITIA_FLEET: readonly PilotKillCount[] = [
    { characterId: 2_114_993_571, name: 'Twan Molenaar', killmails: 50 },
    { characterId: 1_444_365_537, name: 'Tasha Bailey', killmails: 37 },
    { characterId: 1_173_806_786, name: 'Annah Kitheran', killmails: 35 },
    { characterId: 2_118_645_041, name: 'Kiki Of Merri', killmails: 31 },
    { characterId: 2_117_059_479, name: 'MiniSpartan', killmails: 26 },
    { characterId: 1_276_025_316, name: 'Phoochka', killmails: 26 },
    { characterId: 2_112_149_192, name: 'Kong iBUN', killmails: 25 },
    { characterId: 1_566_368_814, name: 'Tomas Bailey', killmails: 25 },
    { characterId: 92_361_974, name: 'Dima Volenkov', killmails: 22 },
    { characterId: 2_118_274_002, name: 'Aith of Merri', killmails: 20 },
]

export const MILITIA_PILOTS_ON_BOARD = 307

export type ShipCount = { typeId: number; name: string; count: number }

export const SHIPS_DESTROYED_HULLS: readonly ShipCount[] = [
    { typeId: 73_794, name: 'Thrasher Fleet Issue', count: 84 },
    { typeId: 16_242, name: 'Thrasher', count: 75 },
    { typeId: 587, name: 'Rifter', count: 71 },
    { typeId: 29_344, name: 'Exequror Navy Issue', count: 63 },
    { typeId: 597, name: 'Punisher', count: 62 },
    { typeId: 73_796, name: 'Catalyst Navy Issue', count: 54 },
    { typeId: 17_703, name: 'Imperial Navy Slicer', count: 41 },
    { typeId: 17_841, name: 'Federation Navy Comet', count: 39 },
    { typeId: 593, name: 'Tristan', count: 37 },
    { typeId: 17_713, name: 'Stabber Fleet Issue', count: 35 },
]

/**
 * Attacker ship_type_id appearances on Auga ship kills (capsules excluded)
 * where faction_id = 500002 (Minmatar militia). 12–18 Jul YC128 UTC.
 */
export const MILITIA_SHIPS_FLOWN_HULLS: readonly ShipCount[] = [
    { typeId: 17_713, name: 'Stabber Fleet Issue', count: 301 },
    { typeId: 73_794, name: 'Thrasher Fleet Issue', count: 219 },
    { typeId: 72_872, name: 'Prophecy Navy Issue', count: 105 },
    { typeId: 24_696, name: 'Harbinger', count: 104 },
    { typeId: 29_344, name: 'Exequror Navy Issue', count: 91 },
    { typeId: 16_242, name: 'Thrasher', count: 80 },
    { typeId: 12_019, name: 'Sacrilege', count: 78 },
    { typeId: 17_709, name: 'Omen Navy Issue', count: 70 },
    { typeId: 29_337, name: 'Augoror Navy Issue', count: 68 },
    { typeId: 35_683, name: 'Hecate', count: 59 },
]

export type AllianceStanding = {
    allianceId: number
    name: string
    killmails: number
    shipsLost: number
    iskDestroyed: number
    iskLost: number
}

export const TOP_ALLIANCES: readonly AllianceStanding[] = [
    {
        allianceId: 99_011_978,
        name: 'Minmatar Fleet Alliance',
        killmails: 397,
        shipsLost: 300,
        iskDestroyed: 28_800_000_000,
        iskLost: 21_500_000_000,
    },
    {
        allianceId: 99_010_995,
        name: 'Empyrean Edict',
        killmails: 276,
        shipsLost: 113,
        iskDestroyed: 18_100_000_000,
        iskLost: 8_300_000_000,
    },
    {
        allianceId: 99_015_016,
        name: 'Slide On Contact',
        killmails: 238,
        shipsLost: 108,
        iskDestroyed: 22_100_000_000,
        iskLost: 8_700_000_000,
    },
    {
        allianceId: 99_014_920,
        name: "Spaghetti N' Meatballs",
        killmails: 186,
        shipsLost: 29,
        iskDestroyed: 18_000_000_000,
        iskLost: 2_800_000_000,
    },
    {
        allianceId: 99_005_678,
        name: 'Local Is Primary',
        killmails: 151,
        shipsLost: 34,
        iskDestroyed: 16_400_000_000,
        iskLost: 1_600_000_000,
    },
]

/**
 * IDs for empire / pirate logos on images.evetech.net corporations/{id}/logo.
 * NPC faction logos use the faction ID (not a member corp) — see ESI image server docs.
 */
export const FACTION_CORP = {
    minmatar: 1_000_134,
    amarr: 1_000_084,
    /** Angel Cartel faction (500011) — not Archangels corp 1000124 */
    angel: 500_011,
    /** CONCORD — neutral / third-party mark */
    concord: 1_000_125,
} as const

export type CampaignHeadlineCategory = 'propaganda' | 'aar' | 'video'

export type CampaignHeadline = {
    title: string
    url: string
    date: string
    category: CampaignHeadlineCategory
    backgroundImage: string
    upvotes: number
    comments: number
    views?: string | number
}

export const HEADLINE_BACKGROUNDS = [
    '/images/combatlog-tile-background.webp',
    '/images/warzone-card.jpg',
    '/images/advocate-card.jpg',
    '/images/propaganda-cover.jpg',
] as const

/**
 * r/Eve headlines tied to the Hed / Auga push (Reddit created_utc + score via Arctic Shift).
 */
export const HEADLINES: readonly CampaignHeadline[] = [
    {
        title: 'EXTRA! EXTRA! THE RATS ARE BACK TO AMAMAKE! RIP DNG! THE PET WARS RAGE ON!!!',
        url: 'https://www.reddit.com/r/Eve/comments/1uy7sl0/extra_extra_the_rats_are_back_to_amamake_rip_dng/',
        date: '2026-07-16',
        category: 'propaganda',
        backgroundImage: HEADLINE_BACKGROUNDS[3],
        upvotes: 49,
        comments: 6,
    },
    {
        title: 'Minmatar Fleet Alliance brawls in Amamake. DNG birthday brawl.',
        url: 'https://youtu.be/6OZd594h2CM',
        date: '2026-07-12',
        category: 'video',
        backgroundImage: '/images/auga-amamake-brawl-thumb.jpg',
        upvotes: 35,
        comments: 10,
    },
    {
        title: 'VICTORY FOR MINMIL IN VARD! AMARR IS OUT OF HED!!!',
        url: 'https://www.reddit.com/r/Eve/comments/1tyn0xy/victory_for_minmil_in_vard_amarr_is_out_of_hed/',
        date: '2026-06-06',
        category: 'aar',
        backgroundImage: HEADLINE_BACKGROUNDS[0],
        upvotes: 57,
        comments: 24,
    },
    {
        title: 'JOIN THE FLEETS! GET STARKMAN BACK!!!',
        url: 'https://www.reddit.com/r/Eve/comments/1tv2886/join_the_fleets_get_starkman_back/',
        date: '2026-06-02',
        category: 'propaganda',
        backgroundImage: HEADLINE_BACKGROUNDS[2],
        upvotes: 30,
        comments: 3,
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
