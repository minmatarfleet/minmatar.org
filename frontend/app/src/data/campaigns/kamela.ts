/**
 * Kamela Fortizar brawl · 29 Aug YC128 · 18:18–22:48 UTC
 *
 * The climax of the Minmatar push south. Figures are computed from the cached
 * zKillboard killmails for Kamela (30003069) in the 29 Aug battle window
 * (capsules excluded); narrative from the "AAR: 350b down in Kamela" report.
 * Sides: Minmatar = Minmatar Fleet + militia; Amarr = CVA + The Curatores
 * Veritatis Auxiliary (RMC) + militia; other = the third parties who piled in.
 */

export const SOLAR_SYSTEM_ID = 30_003_069
export const ZKILL_SYSTEM_URL = `https://zkillboard.com/system/${SOLAR_SYSTEM_ID}/`

/** Reddit AAR that this focus links out to (no internal campaign page). */
export const AAR_URL =
    'https://www.reddit.com/r/Eve/comments/1w21ozl/aar_350b_down_in_kamela/'
/** Peak-hour battle report on evetools. */
export const BATTLE_REPORT_URL = 'https://br.evetools.org/related/30003069/202608291900'

export const BATTLE_DATE = '2026-08-29'
export const WINDOW_LABEL = '29 Aug · Kamela Fortizar'

/** Ship kills only (capsules excluded), whole 29 Aug brawl. */
export const SHIPS_DESTROYED = 381
export const CAMPAIGN_ISK_DESTROYED = 342_500_000_000
export const UNIQUE_PILOTS = 1_065

export const MINMATAR_PILOTS = 179
export const AMARR_PILOTS = 174

/** Losses by victim side (ships + ISK). Sides sum to the battle totals. */
export const MINMATAR_DESTROYED_SHIPS = 60
export const MINMATAR_DESTROYED_ISK = 82_900_000_000
export const AMARR_DESTROYED_SHIPS = 133
export const AMARR_DESTROYED_ISK = 145_200_000_000
export const OTHER_DESTROYED_SHIPS = 188
export const OTHER_DESTROYED_ISK = 114_400_000_000

/** Capital hulls that went down — FL33T's cheap T1 dreads led the count. */
export const REVELATIONS_LOST = 17

export const ENGAGEMENT_MIX = [
    { label: 'Fleet (11+)', value: 243 },
    { label: 'Small gang (2–10)', value: 103 },
    { label: 'Solo', value: 35 },
] as const

export type ShipCount = { typeId: number; name: string; count: number }

/** Most-destroyed hulls in the brawl (capsules excluded). */
export const SHIPS_DESTROYED_HULLS: readonly ShipCount[] = [
    { typeId: 17_732, name: 'Tempest Fleet Issue', count: 45 },
    { typeId: 24_692, name: 'Tornado', count: 22 },
    { typeId: 601, name: 'Ibis', count: 19 },
    { typeId: 29_990, name: 'Loki', count: 19 },
    { typeId: 639, name: 'Tempest', count: 17 },
    { typeId: 19_720, name: 'Revelation', count: 17 },
    { typeId: 47_269, name: 'Kikimora', count: 10 },
    { typeId: 52_907, name: 'Zirnitra', count: 9 },
    { typeId: 19_726, name: 'Phoenix', count: 8 },
    { typeId: 24_698, name: 'Drake', count: 8 },
]

export function formatIsk(isk: number): string {
    if (isk >= 1_000_000_000_000) return `${(isk / 1_000_000_000_000).toFixed(2)}T`
    if (isk >= 1_000_000_000) return `${(isk / 1_000_000_000).toFixed(1)}B`
    if (isk >= 1_000_000) return `${(isk / 1_000_000).toFixed(0)}M`
    return `${(isk / 1_000).toFixed(0)}K`
}
