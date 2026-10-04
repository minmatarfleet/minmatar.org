/**
 * Amamake birthday brawl · 26–27 Sep YC128 · 22:00–03:00 UTC
 *
 * INIT's birthday brawl at the Amamake sun. Figures are computed from the
 * cached zKillboard killmails for Amamake (30002537) in that window (capsules
 * and NPC-only kills excluded). Sides are the victim's militia faction;
 * everyone else is "other". Narrative from "AAR: 625B down in Amamake".
 */

export const SOLAR_SYSTEM_ID = 30_002_537
export const ZKILL_SYSTEM_URL = `https://zkillboard.com/system/${SOLAR_SYSTEM_ID}/`

/** Reddit AAR this focus links out to (no internal campaign page). */
export const AAR_URL = 'https://www.reddit.com/r/Eve/comments/1wr8ohf/aar_625b_down_in_amamake/'
/** Battle report linked from that AAR. */
export const BATTLE_REPORT_URL = 'https://warbeacon.net/br/report/be7a6121-ae41-4793-81d1-108dd1254743'

export const BATTLE_DATE = '2026-09-26'
export const WINDOW_LABEL = '26 Sep · Amamake sun'

/** Ship kills only (capsules excluded), 26 Sep 22:00 through 27 Sep 03:00 UTC. */
export const SHIPS_DESTROYED = 1_612
export const CAMPAIGN_ISK_DESTROYED = 631_402_820_462
export const UNIQUE_PILOTS = 1_653

export const MINMATAR_PILOTS = 222
export const AMARR_PILOTS = 63

/** Losses by victim side (ships + ISK). Sides sum to the battle totals. */
export const MINMATAR_DESTROYED_SHIPS = 274
export const MINMATAR_DESTROYED_ISK = 186_011_845_690
export const AMARR_DESTROYED_SHIPS = 89
export const AMARR_DESTROYED_ISK = 3_202_299_180
export const OTHER_DESTROYED_SHIPS = 1_249
export const OTHER_DESTROYED_ISK = 442_188_675_592

/** Dreadnought hulls that went down in the window. */
export const DREADNOUGHTS_LOST = 24

export const ENGAGEMENT_MIX = [
    { label: 'Fleet (11+)', value: 838 },
    { label: 'Small gang (2–10)', value: 629 },
    { label: 'Solo', value: 145 },
] as const
