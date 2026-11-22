// Fixtures for Features/Intel and combat: affiliation database rows, d-scan feed,
// structure timers and pings, combat logs. Types are the blocks' own prop types, so
// `npm run check` fails when the API or the props move. Systems and hulls come from
// rust/fixtures/sde.json.
import type {
    IntelAffiliation,
    IntelEntitySearchResult,
    IntelMemberCrosscheck,
    IntelPartner,
    IntelRecentItem,
    MoonMetenoxKill,
    MoonProfit,
    StructurePing,
} from '@dtypes/api.minmatar.org'
import type { FleetCombatLog, RepairsUI, StructureTimerUI } from '@dtypes/layout_components'
import type { SavedCombatLog } from '@dtypes/api.minmatar.org'
import { EVE } from '../../stories/_controls'

// ---- time helpers -------------------------------------------------------------------
// Timers and feeds are relative to now so "expired", "2m ago" and countdowns stay true.
const MINUTE = 60_000
const HOUR = 60 * MINUTE
export const minutes_ago = (n: number) => new Date(Date.now() - n * MINUTE).toISOString()
export const hours_from_now = (n: number) => new Date(Date.now() + n * HOUR).toISOString()
export const hours_ago = (n: number) => new Date(Date.now() - n * HOUR).toISOString()

// ---- shared EVE refs ----------------------------------------------------------------
export const BLOCS = {
    snuffed_out:    { id: 3, name: 'Snuffed Out' },
    pandemic:       { id: 7, name: 'Pandemic Horde' },
    goons:          { id: 11, name: 'Goonswarm Federation' },
    fraternity:     { id: 14, name: 'Fraternity.' },
}
export const ENTITIES = {
    snuffed_out:    { kind: 'alliance', id: 99010079, name: 'Snuffed Out' },
    brave:          { kind: 'alliance', id: 99003214, name: 'Brave Collective' },
    pen_is_mightier: { kind: 'corporation', id: 98524611, name: 'Pen Is Mightier' },
    keldar:         { kind: 'character', id: EVE.character_id, name: EVE.character_name },
    dead_scout:     { kind: 'character', id: 2119873420, name: 'Dead Drop Scout' },
    long_name:      { kind: 'corporation', id: 98611001, name: 'The Imperial Fedo Navy Reserve Auxiliary Logistics and Hauling Cooperative of Heimatar' },
}

// ---- IntelAffiliationRow ------------------------------------------------------------
const base_affiliation: IntelAffiliation = {
    id: 4101,
    entity: ENTITIES.snuffed_out,
    bloc: { ...BLOCS.goons, likely: false },
    relation: 'pet',
    status: 'suggested',
    source: 'inferred',
    confidence: 0.82,
    ended: false,
    decided_by: null,
    decided_at: null,
    first_month: '2025-11-01',
    last_month: '2026-10-01',
    note: '',
    evidence: {
        partner_name: 'Goonswarm Federation',
        share: 0.202,
        months_together: 12,
        months_active: 12,
        reverse_share: 0.019,
        shared: 429,
        against: 0,
        militia_shared: 31,
    },
}

export const affiliation_suggested: IntelAffiliation = base_affiliation

export const affiliation_confirmed: IntelAffiliation = {
    ...base_affiliation,
    id: 4102,
    entity: ENTITIES.pen_is_mightier,
    bloc: { ...BLOCS.pandemic, likely: false },
    relation: 'ally',
    status: 'confirmed',
    source: 'inferred',
    confidence: 0.94,
    decided_by: 'Bear That Cares',
    decided_at: '2026-11-03T18:22:10Z',
    evidence: { ...base_affiliation.evidence, partner_name: 'Pandemic Horde', share: 0.46, shared: 1180 },
}

export const affiliation_rejected: IntelAffiliation = {
    ...base_affiliation,
    id: 4103,
    entity: ENTITIES.brave,
    relation: 'associate',
    status: 'rejected',
    confidence: 0.31,
    decided_by: 'Rattini Analyst',
    decided_at: '2026-10-28T09:05:00Z',
    note: 'They shoot each other every week.',
    evidence: { ...base_affiliation.evidence, share: 0.04, months_together: 3, shared: 38, against: 22, militia_shared: 0 },
}

export const affiliation_ended: IntelAffiliation = {
    ...base_affiliation,
    id: 4104,
    entity: ENTITIES.dead_scout,
    relation: 'alt',
    status: 'confirmed',
    ended: true,
    decided_by: 'Bear That Cares',
    decided_at: '2026-02-11T12:00:00Z',
    first_month: '2025-01-01',
    last_month: '2026-04-01',
}

export const affiliation_manual: IntelAffiliation = {
    ...base_affiliation,
    id: 4105,
    entity: ENTITIES.keldar,
    bloc: { ...BLOCS.fraternity, likely: false },
    relation: 'member',
    status: 'confirmed',
    source: 'manual',
    confidence: 1,
    decided_by: 'Bear That Cares',
    decided_at: '2026-11-01T10:00:00Z',
    first_month: null,
    last_month: null,
    note: 'Seen in their Discord.',
    evidence: {},
}

export const affiliation_pilot_associate: IntelAffiliation = {
    ...base_affiliation,
    id: 4106,
    entity: ENTITIES.dead_scout,
    bloc: { ...BLOCS.snuffed_out, likely: true },
    relation: 'associate',
    confidence: 0.67,
    evidence: { shared: 57, months_together: 5, flies_for: null },
}

export const affiliation_long_name: IntelAffiliation = {
    ...base_affiliation,
    id: 4107,
    entity: ENTITIES.long_name,
    confidence: 0.5,
}

// ---- IntelEntitySearchResults -------------------------------------------------------
export const search_results: IntelEntitySearchResult[] = [
    { kind: 'alliance', id: 99010079, name: 'Snuffed Out', status: 'done', bloc: { ...BLOCS.goons, likely: false } },
    { kind: 'corporation', id: 98524611, name: 'Snuffed Out Logistics', status: 'investigating', bloc: { ...BLOCS.snuffed_out, likely: true } },
    { kind: 'character', id: 2119873420, name: 'Snuffed Scout', status: 'queued', bloc: null },
    { kind: 'character', id: 2119873421, name: 'Snuff Hauler Two', status: 'new', bloc: null },
    { kind: 'corporation', id: 98611001, name: 'Snuffbox Industries', status: 'failed', bloc: null },
]

// ---- IntelMembersTable --------------------------------------------------------------
export const members_crosscheck: IntelMemberCrosscheck[] = [
    {
        character_id: 2119873501, character_name: 'Auga Defender', main_character_name: null,
        bloc: { ...BLOCS.goons, likely: false }, shared: 64, months_together: 6, last_month: '2026-10-01',
        groups: [{ kind: 'alliance', id: 99010079, name: 'Snuffed Out' }, { kind: 'corporation', id: 98524611, name: 'Pen Is Mightier' }],
    },
    {
        character_id: 2119873502, character_name: 'Rens Gatecamper', main_character_name: 'Kel\'dar Atram',
        bloc: { ...BLOCS.pandemic, likely: true }, shared: 21, months_together: 3, last_month: '2026-09-01',
        groups: [{ kind: 'alliance', id: 99003214, name: 'Brave Collective' }],
    },
    {
        character_id: 2119873503, character_name: 'Hek Trader Alt', main_character_name: 'Hek Trader Alt',
        bloc: { ...BLOCS.fraternity, likely: false }, shared: 9, months_together: 1, last_month: '2026-10-01',
        groups: [],
    },
    {
        character_id: 2119873504, character_name: 'A Pilot With An Exceedingly Long Name Indeed', main_character_name: 'Another Very Long Main Character Name',
        bloc: { id: 21, name: 'The Imperial Fedo Navy Reserve Auxiliary Logistics Bloc', likely: false }, shared: 1280, months_together: 12, last_month: '2026-10-01',
        groups: Object.values(ENTITIES).slice(0, 3),
    },
]

// ---- IntelPartnersTable -------------------------------------------------------------
const partner = (n: number, over: Partial<IntelPartner> = {}): IntelPartner => ({
    kind: n % 3 === 0 ? 'corporation' : 'alliance',
    id: 99010000 + n,
    name: `Partner Group ${n}`,
    share: Math.max(0.01, 0.4 - n * 0.025),
    shared: Math.max(3, 600 - n * 45),
    months_together: Math.max(1, 12 - n),
    against: n % 4 === 0 ? n : 0,
    militia_shared: n % 2 === 0 ? n * 3 : 0,
    last_month: '2026-10-01',
    bloc: n % 5 === 0 ? null : { ...BLOCS.goons, likely: n % 3 === 0 },
    ...over,
})
export const partners_few: IntelPartner[] = [
    partner(1, { name: 'Snuffed Out', share: 0.202 }),
    partner(2, { name: 'Pen Is Mightier', share: 0.087, bloc: { ...BLOCS.pandemic, likely: false } }),
    partner(3, { name: 'Brave Collective', share: 0.0004, against: 22, militia_shared: 0, bloc: null }),
]
export const partners_busy: IntelPartner[] = Array.from({ length: 14 }, (_, i) => partner(i + 1))
export const partners_pilot: IntelPartner[] = partners_few.map((row) => ({ ...row, share: null }))

// ---- DscanRecentList ----------------------------------------------------------------
const ship = (type_id: number, name: string, count: number) => ({ type_id, name, count })
export const recent_items: IntelRecentItem[] = [
    {
        id: 'r1', kind: 'dscan', report_id: 'a8f3k2', system_id: 30002537, system_name: 'Amamake', occurred_at: minutes_ago(4),
        count: 38, image: null, is_ping: false, note: '', source: 'Kel\'dar Atram', summary: '38 ships', standings: null,
        ships: [ship(24702, 'Hurricane', 14), ship(11978, 'Scimitar', 4), ship(11999, 'Vagabond', 6), ship(622, 'Stabber', 9), ship(587, 'Rifter', 5)],
    },
    {
        id: 'r2', kind: 'local', report_id: 'b71x9q', system_id: 30002542, system_name: 'Auga', occurred_at: minutes_ago(11),
        count: 52, image: { kind: 'corporation', id: EVE.corporation_id }, is_ping: false, note: '', source: 'Rens Gatecamper', summary: '52 pilots',
        standings: { hostile: 17, friendly: 31, neutral: 4 }, ships: [],
    },
    {
        id: 'r3', kind: 'dscan', report_id: null, system_id: 30005000, system_name: 'Old Man Star', occurred_at: minutes_ago(47),
        count: 6, image: null, is_ping: true, note: '', source: 'Intel channel ping', summary: 'Cap sighted: Vargur',
        standings: null, ships: [ship(28665, 'Vargur', 1)],
    },
    {
        id: 'r4', kind: 'local', report_id: 'c02m4d', system_id: 30002053, system_name: 'Hek', occurred_at: hours_ago(1.6),
        count: 9, image: null, is_ping: false, note: '', source: 'Hek Trader Alt', summary: '9 pilots',
        standings: { hostile: 0, friendly: 9 }, ships: [],
    },
]

// ---- StructureTimerList / StructurePingsPanel ---------------------------------------
const timer = (id: number, over: Partial<StructureTimerUI>): StructureTimerUI => ({
    id,
    name: 'Rattini Hold',
    state: 'armor',
    timer: hours_from_now(6),
    system_name: 'Amamake',
    alliance_id: EVE.alliance_id,
    alliance_name: EVE.alliance_name,
    corporation_name: EVE.corporation_name,
    structure_id: 1042400000000 + id,
    structure_type: 'Fortizar',
    structure_type_id: 35833,
    verified: true,
    ...over,
})
export const timer_verified = timer(501, {})
export const timer_unverified = timer(502, { name: 'Forward Docking', structure_type: 'Astrahus', structure_type_id: 35832, system_name: 'Auga', state: 'hull', timer: hours_from_now(27), verified: false })
export const timer_expired = timer(503, { name: 'Old Anchor', structure_type: 'Athanor', structure_type_id: 35835, system_name: 'Rens', state: 'anchoring', timer: hours_ago(3), verified: false })
export const timer_unknown_owner = timer(504, { name: 'Unscanned Citadel', structure_type: 'Raitaru', structure_type_id: 35825, system_name: 'Old Man Star', alliance_name: null, corporation_name: null, structure_id: null, verified: false, timer: hours_from_now(52) })
export const timer_long_name = timer(505, { name: 'The Imperial Fedo Navy Reserve Auxiliary Logistics Staging Citadel Alpha', system_name: 'Egbinger', timer: hours_from_now(13) })
export const timers_typical: StructureTimerUI[] = [timer_verified, timer_unverified, timer_expired]
export const timers_busy: StructureTimerUI[] = Array.from({ length: 12 }, (_, i) =>
    timer(600 + i, {
        name: ['Rattini Hold', 'Forward Docking', 'Hek Market Hub', 'Auga Refinery', 'Rens Trade Post', 'Uedama Gate Tower'][i % 6],
        system_name: ['Amamake', 'Auga', 'Hek', 'Auga', 'Rens', 'Uedama'][i % 6],
        structure_type: ['Fortizar', 'Astrahus', 'Keepstar', 'Tatara', 'Azbel', 'Sotiyo'][i % 6],
        structure_type_id: [35833, 35832, 35834, 35836, 35826, 35827][i % 6],
        state: ['armor', 'hull', 'anchoring', 'unanchoring'][i % 4],
        timer: i % 5 === 4 ? hours_ago(i) : hours_from_now(2 + i * 5),
        verified: i % 3 !== 0,
    }))

const ping = (id: number, minutes: number, notification_type: string, summary: string, discord_success = true): StructurePing => ({
    id, created_at: minutes_ago(minutes), event_time: minutes_ago(minutes), notification_type, summary, discord_success, structure_id: 1042400000501,
})
export const pings_typical: StructurePing[] = [
    ping(9001, 6, 'StructureUnderAttack', 'Rattini Hold (Amamake) is under attack: shield at 82%'),
    ping(9002, 38, 'StructureLostShields', 'Rattini Hold (Amamake) lost shields; armor timer set'),
    ping(9003, 190, 'StructureAnchoring', 'Forward Docking (Auga) started anchoring', false),
    ping(9004, 1500, 'StructureLostArmor', 'Hek Market Hub (Hek) lost armor; hull timer set'),
    ping(9005, 2900, 'StructureFuelAlert', 'Auga Refinery (Auga) has under 24 hours of fuel left', false),
    ping(9006, 4300, 'StructureServicesOffline', 'Rens Trade Post (Rens) services went offline'),
]
export const pings_all_posted: StructurePing[] = pings_typical.map((row) => ({ ...row, discord_success: true }))
export const pings_busy: StructurePing[] = Array.from({ length: 40 }, (_, i) =>
    ping(9100 + i, 10 + i * 55, ['StructureUnderAttack', 'StructureLostShields', 'StructureFuelAlert', 'StructureWentLowPower'][i % 4],
        `${['Rattini Hold', 'Forward Docking', 'Auga Refinery', 'Rens Trade Post'][i % 4]} (${['Amamake', 'Auga', 'Auga', 'Rens'][i % 4]}) alert ${i + 1}`, i % 7 !== 0))

// ---- FleetCombatLogTable / CombatLogItem --------------------------------------------
const fleet_log = (id: number, over: Partial<FleetCombatLog> = {}): FleetCombatLog => ({
    id,
    uploaded_at: new Date(Date.now() - id * 3 * HOUR),
    user_id: 100 + id,
    logger: { character_id: EVE.character_id - id, character_name: ['Kel\'dar Atram', 'Rattini Logi One', 'Amamake Anchor', 'Auga Scout'][id % 4] },
    character_name: ['Muninn', 'Scimitar', 'Hurricane', 'Vagabond'][id % 4] + ' pilot',
    system_name: ['Amamake', 'Auga', 'Rens', 'Hek'][id % 4],
    ...over,
})
export const fleet_logs_one: FleetCombatLog[] = [fleet_log(1)]
export const fleet_logs_typical: FleetCombatLog[] = [fleet_log(1), fleet_log(2), fleet_log(3), fleet_log(4)]
export const fleet_logs_busy: FleetCombatLog[] = Array.from({ length: 18 }, (_, i) => fleet_log(i + 1))
export const fleet_logs_edge: FleetCombatLog[] = [
    fleet_log(1, { character_name: '', system_name: '' }),
    fleet_log(2, { logger: { character_id: EVE.character_id, character_name: 'A Logger With An Extremely Long Character Name Here' }, character_name: 'Another Extremely Long Flown Character Name' }),
]

const saved_log = (id: number, over: Partial<SavedCombatLog>): SavedCombatLog => ({
    id, uploaded_at: new Date(Date.now() - id * 5 * HOUR), user_id: 100, fleet_id: 0, fitting_id: 0, character_name: EVE.character_name, system_name: 'Amamake', ...over,
})
export const saved_log_fleet = saved_log(71, { fleet_id: 92221 })
export const saved_log_fitting = saved_log(72, { fitting_id: 3150 })
export const saved_log_solo = saved_log(73, {})

// ---- RepairBadge --------------------------------------------------------------------
export const repair_armor: RepairsUI = {
    name: 'Large Armor Repairer II', rep_type: 'armor', cycles: 214, amount_repaired: 1_268_400, max_cycle: 6_320, avg_cycle: 5_927, effective_reps: 94.2, item_id: 3538,
}
export const repair_shield: RepairsUI = {
    name: 'Medium Shield Booster II', rep_type: 'shield', cycles: 96, amount_repaired: 148_200, max_cycle: 1_650, avg_cycle: 1_544, effective_reps: 61.5, item_id: 10850,
}
export const repair_remote: RepairsUI = {
    name: 'Large Remote Armor Repairer II', rep_type: 'armor', cycles: 340, amount_repaired: 2_480_000, max_cycle: 7_400, avg_cycle: 7_294, effective_reps: 100, item_id: 3544,
}
export const repair_wasted: RepairsUI = {
    name: 'Medium Remote Hull Repairer I', rep_type: 'hull', cycles: 12, amount_repaired: 3_100, max_cycle: 410, avg_cycle: 258, effective_reps: 0, item_id: 3550,
}

// ---- Alpine shim for XFadeScroll (the site's footer scripts define it) ---------------
export function ensure_edge_fade() {
    const w = globalThis as any
    if (w.edge_fade) return
    w.edge_fade = () => ({
        init() {
            const el = (this as any).$el as HTMLElement
            const update = () => {
                el.classList.toggle('fade-start', el.scrollLeft > 0)
                el.classList.toggle('fade-end', el.scrollLeft + el.clientWidth < el.scrollWidth - 1)
            }
            update()
            if (typeof ResizeObserver !== 'undefined') new ResizeObserver(update).observe(el)
            el.addEventListener('scroll', update, { passive: true })
        },
    })
}

// ---- moons (Universe > Moons row tabs) ---------------------------------------------
// An R16 moon priced on a Jita snapshot: 1.14b output, 365M fuel, 777M net.
export const moon_profit_r16: MoonProfit = {
    output: [
        { name: 'Platinum', units: 93_312, price: 7_914, isk: 738_471_168 },
        { name: 'Pyerite', units: 12_268_800, price: 17.71, isk: 217_280_448 },
        { name: 'Mexallon', units: 1_831_680, price: 51.56, isk: 94_441_421 },
        { name: 'Silicates', units: 196_560, price: 354.6, isk: 69_700_176 },
        { name: 'Evaporite Deposits', units: 124_416, price: 183.3, isk: 22_805_453 },
    ],
    fuel: [
        { name: 'Magmatic Gas', units: 144_000, price: 2_100, isk: 302_400_000 },
        { name: 'Nitrogen Fuel Block', units: 3_600, price: 17_460, isk: 62_856_000 },
    ],
    priced_at: hours_ago(2),
}
export const moon_net_r16 = 777_442_666

// An R4 moon whose fuel costs more than it makes.
export const moon_profit_r4_loss: MoonProfit = {
    output: [
        { name: 'Pyerite', units: 3_456_000, price: 17.71, isk: 61_205_760 },
        { name: 'Mexallon', units: 172_800, price: 51.56, isk: 8_909_568 },
        { name: 'Atmospheric Gases', units: 5_616, price: 790, isk: 4_436_640 },
    ],
    fuel: moon_profit_r16.fuel,
    priced_at: hours_ago(2),
}
export const moon_net_r4_loss = -290_903_032

const day_ms = 24 * HOUR
const days_ago = (n: number) => new Date(Date.now() - n * day_ms).toISOString()

export const metenox_kills_two: MoonMetenoxKill[] = [
    {
        killmail_id: 131_204_118,
        killed_at: days_ago(12),
        owner_corporation_id: 98_000_101,
        owner_corporation_name: 'Holder Corp B',
        owner_alliance_id: 99_000_201,
        owner_alliance_name: 'Holder Alliance B',
        killer_id: 99_000_301,
        killer_name: 'Attacker Alliance X',
        attacker_count: 34,
    },
    {
        killmail_id: 129_877_402,
        killed_at: days_ago(93),
        owner_corporation_id: 98_000_102,
        owner_corporation_name: 'Holder Corp A',
        owner_alliance_id: null,
        owner_alliance_name: '',
        killer_id: 99_000_201,
        killer_name: 'Holder Alliance B',
        attacker_count: 12,
    },
]
