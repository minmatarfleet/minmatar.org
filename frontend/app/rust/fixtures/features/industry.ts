// Fixtures for the Industry feature stories (rust/stories/features/industry/).
// Typed with the blocks' own prop types so `npm run check` fails when the API or the props change.
import type {
    BuybackContract,
    FreightContract,
    Product,
    ProductBuild,
    ProductBuildMaterial,
    ProductInsights,
    ProductOrderLine,
    ProductRunningJob,
} from '@dtypes/api.minmatar.org'
import type { CargoItem, IndustryOrderUI, OrderLocation } from '@dtypes/layout_components'
import { EVE } from '../../stories/_controls'

// Dates are relative to "now" so deadlines and claim windows stay in the state the story is about.
const DAY = 86_400_000
const HOUR = 3_600_000
export const iso_from_now = (ms: number): string => new Date(Date.now() + ms).toISOString()
export const day_from_now = (days: number): string => iso_from_now(days * DAY).slice(0, 10)

// ---------------------------------------------------------------------------
// People
// ---------------------------------------------------------------------------
export const builders = [
    { id: EVE.character_id, name: EVE.character_name },
    { id: 2112954533, name: 'Rattini Pilot' },
    { id: 2112954534, name: 'Hek Roamer' },
    { id: 2112954535, name: 'Amamake Defender' },
    { id: 2112954536, name: 'Auga Hauler' },
    { id: 2112954537, name: 'Vard Miner' },
]
const [kel, rattini, hek, amamake, auga, vard] = builders

// ---------------------------------------------------------------------------
// Product build (one run at Jita prices): ProductBuildCost, ProductBuildMaterials
// ---------------------------------------------------------------------------
type MaterialSeed = [type_id: number, name: string, quantity: number, unit_price: number | null, strategy: string | null, product_id?: number]

const TRITANIUM = 34
const PYERITE = 35
const MEXALLON = 36
const ISOGEN = 37
const NOCXIUM = 38
const ZYDRINE = 39
const MEGACYTE = 40

const material = ([type_id, name, quantity, unit_price, strategy, product_id]: MaterialSeed): ProductBuildMaterial => ({
    type_id,
    name,
    quantity,
    unit_price,
    line_cost: unit_price === null ? null : Math.round(unit_price * quantity),
    strategy,
    industry_product_id: product_id ?? null,
})

const make_build = (
    seed: Pick<ProductBuild, 'product_id' | 'type_id' | 'blueprint_type_id' | 'activity'>
        & Partial<Pick<ProductBuild, 'products_per_run' | 'time_seconds' | 'invention' | 'invention_cost'>>
        & { sell_price: number | null; materials: MaterialSeed[] },
): ProductBuild => {
    const materials = seed.materials.map(material)
    const complete = materials.every(line => line.line_cost !== null)
    const material_cost = complete ? materials.reduce((sum, line) => sum + (line.line_cost ?? 0), 0) : null
    const products_per_run = seed.products_per_run ?? 1
    const margin = material_cost !== null && seed.sell_price !== null
        ? seed.sell_price * products_per_run - material_cost - (seed.invention_cost ?? 0)
        : null
    return {
        product_id: seed.product_id,
        type_id: seed.type_id,
        blueprint_type_id: seed.blueprint_type_id,
        activity: seed.activity,
        products_per_run,
        time_seconds: seed.time_seconds ?? 0,
        sell_price: seed.sell_price,
        materials,
        prices_complete: complete && seed.sell_price !== null,
        material_cost,
        margin,
        invention: seed.invention ?? null,
        invention_cost: seed.invention_cost ?? null,
    }
}

/** A Rifter: cheap T1 frigate, every material priced and tracked in-house. */
export const build_rifter: ProductBuild = make_build({
    product_id: 4001,
    type_id: EVE.rifter_type_id,
    blueprint_type_id: 691,
    activity: 'manufacturing',
    sell_price: 520_000,
    time_seconds: 6_000,
    materials: [
        [TRITANIUM, 'Tritanium', 22_222, 4.1, 'harvested', 3001],
        [PYERITE, 'Pyerite', 6_667, 10.2, 'harvested', 3002],
        [MEXALLON, 'Mexallon', 1_667, 72.5, 'produced', 3003],
        [ISOGEN, 'Isogen', 222, 118, 'imported'],
    ],
})

/** A Hurricane: bigger run, long build time, one input bought from Jita. */
export const build_hurricane: ProductBuild = make_build({
    product_id: 4002,
    type_id: 24702,
    blueprint_type_id: 24703,
    activity: 'manufacturing',
    sell_price: 71_400_000,
    time_seconds: 3 * 86_400 + 4 * 3_600 + 20 * 60,
    materials: [
        [TRITANIUM, 'Tritanium', 2_333_334, 4.1, 'harvested', 3001],
        [PYERITE, 'Pyerite', 466_667, 10.2, 'harvested', 3002],
        [MEXALLON, 'Mexallon', 116_667, 72.5, 'produced', 3003],
        [ISOGEN, 'Isogen', 23_334, 118, 'imported', 3004],
        [NOCXIUM, 'Nocxium', 3_889, 760, 'imported', 3005],
        [ZYDRINE, 'Zydrine', 778, 1_450, 'imported'],
        [MEGACYTE, 'Megacyte', 389, 2_240, null],
    ],
})

/** A Wolf: T2 hull built from a Rifter, with an invention cost taken off the margin. */
export const build_wolf: ProductBuild = make_build({
    product_id: 4003,
    type_id: 11371,
    blueprint_type_id: 11372,
    activity: 'manufacturing',
    sell_price: 38_900_000,
    time_seconds: 2 * 86_400 + 2 * 3_600,
    invention_cost: 2_150_000,
    invention: {
        kind: 'invention',
        source_name: 'Rifter Blueprint',
        decryptor_name: null,
        chance: 0.34,
        runs_per_copy: 1,
        copy_me: 2,
        copy_te: 4,
        cost_per_unit: 2_150_000,
        sources: [],
    },
    materials: [
        [EVE.rifter_type_id, 'Rifter', 1, 520_000, 'produced', 4001],
        [TRITANIUM, 'Tritanium', 120_000, 4.1, 'harvested', 3001],
        [PYERITE, 'Pyerite', 48_000, 10.2, 'harvested', 3002],
        [MEXALLON, 'Mexallon', 12_000, 72.5, 'produced', 3003],
        [ISOGEN, 'Isogen', 6_400, 118, 'imported', 3004],
        [NOCXIUM, 'Nocxium', 1_800, 760, null],
    ],
})

/** Zydrine has no Jita price yet: the cost total, margin and hint go unknown. */
export const build_missing_prices: ProductBuild = make_build({
    ...build_hurricane,
    sell_price: 71_400_000,
    materials: [
        [TRITANIUM, 'Tritanium', 2_333_334, 4.1, 'harvested', 3001],
        [PYERITE, 'Pyerite', 466_667, 10.2, 'harvested', 3002],
        [ISOGEN, 'Isogen', 23_334, 118, 'imported', 3004],
        [ZYDRINE, 'Zydrine', 778, null, 'imported'],
        [MEGACYTE, 'Megacyte', 389, null, null],
    ],
})

/** Minerals spiked: building loses ISK. */
export const build_loss_making: ProductBuild = make_build({
    ...build_hurricane,
    sell_price: 41_000_000,
    materials: [
        [TRITANIUM, 'Tritanium', 2_333_334, 9.8, 'harvested', 3001],
        [PYERITE, 'Pyerite', 466_667, 24, 'harvested', 3002],
        [MEXALLON, 'Mexallon', 116_667, 190, 'produced', 3003],
        [ISOGEN, 'Isogen', 23_334, 260, 'imported', 3004],
        [NOCXIUM, 'Nocxium', 3_889, 1_480, 'imported', 3005],
        [ZYDRINE, 'Zydrine', 778, 3_100, 'imported'],
    ],
})

/** A batch product: one run makes 100 units. */
export const build_batch: ProductBuild = make_build({
    product_id: 4004,
    type_id: 28668,
    blueprint_type_id: 28669,
    activity: 'manufacturing',
    products_per_run: 100,
    sell_price: 1_850,
    time_seconds: 25 * 60,
    materials: [
        [TRITANIUM, 'Tritanium', 1_500, 4.1, 'harvested', 3001],
        [PYERITE, 'Pyerite', 380, 10.2, 'harvested', 3002],
        [MEXALLON, 'Mexallon', 40, 72.5, 'produced', 3003],
    ],
})

/** A blueprint with an empty bill of materials (SDE gap). */
export const build_no_materials: ProductBuild = make_build({
    product_id: 4005,
    type_id: 11999,
    blueprint_type_id: 12000,
    activity: 'manufacturing',
    sell_price: null,
    materials: [],
})

// ---------------------------------------------------------------------------
// Product insights: ProductBuildQueue
// ---------------------------------------------------------------------------
const order_line = (
    order_id: number,
    code: string,
    who: { id: number; name: string } | null,
    over: Partial<ProductOrderLine>,
): ProductOrderLine => ({
    order_id,
    public_short_code: code,
    character_id: who?.id ?? null,
    character_name: who?.name ?? '',
    created_at: iso_from_now(-6 * DAY),
    needed_by: day_from_now(5),
    fulfilled_at: null,
    quantity: 10,
    assigned: 0,
    delivered: 0,
    ...over,
})

const running_job = (who: { id: number; name: string }, corporation_name: string, units: number, ends_in: number): ProductRunningJob => ({
    character_id: who.id,
    character_name: who.name,
    corporation_name,
    units,
    ends_at: iso_from_now(ends_in),
})

const insights_base = (orders: ProductOrderLine[], running: ProductRunningJob[]): ProductInsights => {
    const open = orders.filter(order => !order.fulfilled_at)
    const open_units = open.reduce((sum, order) => sum + order.quantity, 0)
    const open_assigned_units = open.reduce((sum, order) => sum + order.assigned, 0)
    const open_delivered_units = open.reduce((sum, order) => sum + order.delivered, 0)
    const running_units = running.reduce((sum, job) => sum + job.units, 0)
    return {
        ready: true,
        generated_at: iso_from_now(-35 * 60_000),
        is_ship: true,
        window_days: 90,
        recent_days: 30,
        unit_price: 71_400_000,
        built: {
            units_30d: 58,
            units_90d: 171,
            jobs_90d: 38,
            builders_90d: 5,
            running_units,
            running_jobs: running.length,
            last_built_at: iso_from_now(-9 * HOUR),
        },
        builders: [],
        corporations: [],
        running,
        orders: {
            open_orders: open.length,
            open_units,
            open_assigned_units,
            open_delivered_units,
            ordered_units_90d: 240,
            recent: orders,
        },
        sales: {
            market_units_30d: 12,
            market_units_90d: 31,
            contract_units_30d: 44,
            contract_units_90d: 120,
            listed_units: 18,
            lowest_listed_price: 69_900_000,
            outstanding_contracts: 3,
            locations: [],
        },
        hangars: null,
        losses: null,
        weekly: [],
    }
}

/** Open orders at every stage, plus a fulfilled one the queue leaves out, and four jobs in progress. */
export const insights_busy: ProductInsights = insights_base(
    [
        order_line(8412, 'KX4T9', kel, { quantity: 20, assigned: 0, delivered: 0, needed_by: day_from_now(3) }),
        order_line(8409, 'M27PQ', rattini, { quantity: 15, assigned: 10, delivered: 5, needed_by: day_from_now(6) }),
        order_line(8397, 'B8WZ2', amamake, { quantity: 30, assigned: 30, delivered: 12, needed_by: day_from_now(1) }),
        order_line(8391, 'R5N3D', hek, { quantity: 8, assigned: 2, delivered: 0, needed_by: null }),
        order_line(8350, 'Q9L1C', null, { quantity: 12, assigned: 12, delivered: 12, fulfilled_at: iso_from_now(-2 * DAY), needed_by: day_from_now(-3) }),
    ],
    [
        running_job(rattini, 'Rattini Tribe', 5, 14 * HOUR),
        running_job(amamake, 'Rattini Tribe', 1, 2 * HOUR),
        running_job(auga, 'Snuff Out', 12, 2 * DAY + 3 * HOUR),
        running_job(vard, 'Pulse Tech', 4, 31 * HOUR),
    ],
)

/** No open orders and nothing in production. */
export const insights_idle: ProductInsights = insights_base(
    [order_line(8350, 'Q9L1C', kel, { quantity: 12, assigned: 12, delivered: 12, fulfilled_at: iso_from_now(-2 * DAY) })],
    [],
)

/** Every open unit already has a builder: no "without a builder" count, buttons read View. */
export const insights_all_claimed: ProductInsights = insights_base(
    [
        order_line(8409, 'M27PQ', rattini, { quantity: 15, assigned: 15, delivered: 5 }),
        order_line(8397, 'B8WZ2', amamake, { quantity: 30, assigned: 30, delivered: 12 }),
    ],
    [running_job(rattini, 'Rattini Tribe', 1, 5 * HOUR)],
)

// ---------------------------------------------------------------------------
// Orders: OrderItem, OrdersTable
// ---------------------------------------------------------------------------
const AMAMAKE_STATION = { location_id: 1048961010402, location_name: 'Amamake - Rattini Tribe Freeport' }
const RENS_STATION = { location_id: 60004588, location_name: 'Rens VI - Moon 8 - Brutor Tribe Treasury' }
const AUGA_STATION = { location_id: 1049237464210, location_name: 'Auga - Pulse Tech Citadel' }

const order_ui = (over: Partial<IndustryOrderUI> & Pick<IndustryOrderUI, 'id' | 'items'>): IndustryOrderUI => ({
    created_at: iso_from_now(-5 * DAY),
    needed_by: day_from_now(6),
    fulfilled_at: null,
    public_short_code: `A${String(over.id).padStart(4, '0')}`,
    character_id: kel.id,
    character_name: kel.name,
    location: AMAMAKE_STATION,
    assigned_to: [],
    provisional: false,
    starts_at: null,
    ...over,
})

/** A fresh order with nobody on it yet. */
export const order_unclaimed: IndustryOrderUI = order_ui({
    id: 8412,
    items: [{ eve_type_id: 24702, eve_type_name: 'Hurricane', quantity: 20, target_unit_price: '68000000', estimated_profit_per_unit: 4_200_000 }],
    created_at: iso_from_now(-1 * DAY),
    needed_by: day_from_now(9),
})

/** Several hulls, two builders, due soon. */
export const order_in_progress: IndustryOrderUI = order_ui({
    id: 8409,
    character_id: rattini.id,
    character_name: rattini.name,
    items: [
        { eve_type_id: 24702, eve_type_name: 'Hurricane', quantity: 15, target_unit_price: '68000000', estimated_profit_per_unit: 4_200_000 },
        { eve_type_id: 12015, eve_type_name: 'Muninn', quantity: 5, target_unit_price: '112000000', estimated_profit_per_unit: 7_900_000 },
        { eve_type_id: 11978, eve_type_name: 'Scimitar', quantity: 4, target_unit_price: '98000000', estimated_profit_per_unit: null },
    ],
    assigned_to: [
        { id: amamake.id, name: amamake.name, total_value_isk: 1_020_000_000 },
        { id: auga.id, name: auga.name, total_value_isk: 340_000_000 },
    ],
    needed_by: day_from_now(2),
})

/** Past its deadline and still open. */
export const order_overdue: IndustryOrderUI = order_ui({
    id: 8344,
    character_id: hek.id,
    character_name: hek.name,
    items: [{ eve_type_id: 622, eve_type_name: 'Stabber', quantity: 40, target_unit_price: '8900000', estimated_profit_per_unit: 650_000 }],
    assigned_to: [{ id: vard.id, name: vard.name, total_value_isk: 120_000_000 }],
    created_at: iso_from_now(-12 * DAY),
    needed_by: day_from_now(-3),
    location: RENS_STATION,
})

/** Delivered; the row says when it was completed. */
export const order_fulfilled: IndustryOrderUI = order_ui({
    id: 8301,
    character_id: amamake.id,
    character_name: amamake.name,
    items: [{ eve_type_id: 11999, eve_type_name: 'Vagabond', quantity: 6, target_unit_price: '61000000', estimated_profit_per_unit: 3_500_000 }],
    assigned_to: [{ id: kel.id, name: kel.name, total_value_isk: 366_000_000 }],
    created_at: iso_from_now(-14 * DAY),
    needed_by: day_from_now(-2),
    fulfilled_at: iso_from_now(-3 * DAY),
})

/** Provisional order inside its claiming window: the status reads "Claiming" with the hours left. */
export const order_claiming: IndustryOrderUI = order_ui({
    id: 8420,
    items: [{ eve_type_id: 16231, eve_type_name: 'Cyclone', quantity: 25, target_unit_price: '19500000', estimated_profit_per_unit: 1_100_000 }],
    provisional: true,
    starts_at: iso_from_now(5 * HOUR + 30 * 60_000),
    created_at: iso_from_now(-2 * HOUR),
    needed_by: day_from_now(8),
})

/** An unusually long item list and a very long pilot name, to check wrapping. */
export const order_long: IndustryOrderUI = order_ui({
    id: 8433,
    character_name: "Kel'dar Atram the Third of the Rattini Tribe Freeport Logistics Wing",
    items: [
        { eve_type_id: 587, eve_type_name: 'Rifter', quantity: 60, target_unit_price: '520000', estimated_profit_per_unit: 40_000 },
        { eve_type_id: 17713, eve_type_name: 'Stabber Fleet Issue', quantity: 12, target_unit_price: '42000000', estimated_profit_per_unit: 2_100_000 },
        { eve_type_id: 33157, eve_type_name: 'Hurricane Fleet Issue', quantity: 10, target_unit_price: '88000000', estimated_profit_per_unit: 5_300_000 },
        { eve_type_id: 17720, eve_type_name: 'Cynabal', quantity: 3, target_unit_price: '121000000', estimated_profit_per_unit: 8_800_000 },
        { eve_type_id: 17812, eve_type_name: 'Republic Fleet Firetail', quantity: 30, target_unit_price: '9800000', estimated_profit_per_unit: 400_000 },
        { eve_type_id: 34562, eve_type_name: 'Svipul', quantity: 16, target_unit_price: '34000000', estimated_profit_per_unit: 1_900_000 },
        { eve_type_id: 28665, eve_type_name: 'Vargur', quantity: 2, target_unit_price: '1480000000', estimated_profit_per_unit: 96_000_000 },
    ],
    assigned_to: builders.slice(1).map((pilot, index) => ({ id: pilot.id, name: pilot.name, total_value_isk: (index + 1) * 180_000_000 })),
})

const busy_hulls: [number, string, number, string][] = [
    [587, 'Rifter', 80, '520000'],
    [622, 'Stabber', 30, '8900000'],
    [24702, 'Hurricane', 20, '68000000'],
    [16231, 'Cyclone', 14, '19500000'],
    [11999, 'Vagabond', 6, '61000000'],
    [12015, 'Muninn', 8, '112000000'],
    [11978, 'Scimitar', 5, '98000000'],
    [17713, 'Stabber Fleet Issue', 10, '42000000'],
    [34562, 'Svipul', 12, '34000000'],
    [629, 'Rupture', 18, '11200000'],
    [644, 'Typhoon', 6, '78000000'],
    [11196, 'Claw', 25, '14800000'],
]

/** A busy location: a dozen orders from different pilots at every stage. */
export const orders_busy: IndustryOrderUI[] = busy_hulls.map(([type_id, name, quantity, price], index) => {
    const requester = builders[index % builders.length]
    const assigned = index % 3 === 0 ? [] : builders.slice(index % 5, (index % 5) + 1 + (index % 2)).map(pilot => ({
        id: pilot.id,
        name: pilot.name,
        total_value_isk: (index + 2) * 90_000_000,
    }))
    return order_ui({
        id: 8300 + index * 7,
        character_id: requester.id,
        character_name: requester.name,
        items: [{ eve_type_id: type_id, eve_type_name: name, quantity, target_unit_price: price, estimated_profit_per_unit: Math.round(Number(price) * 0.06) }],
        assigned_to: assigned,
        created_at: iso_from_now(-(3 + index) * DAY),
        needed_by: day_from_now(index - 2),
    })
})

export const location_amamake_busy: OrderLocation = { ...AMAMAKE_STATION, orders: orders_busy }
export const location_amamake_single: OrderLocation = { ...AMAMAKE_STATION, orders: [order_unclaimed] }
export const location_amamake_empty: OrderLocation = { ...AMAMAKE_STATION, orders: [] }
export const location_rens: OrderLocation = { ...RENS_STATION, orders: [order_overdue, order_ui({ id: 8350, items: [{ eve_type_id: 587, eve_type_name: 'Rifter', quantity: 50, target_unit_price: '520000', estimated_profit_per_unit: 40_000 }], location: RENS_STATION })] }
export const location_auga: OrderLocation = { ...AUGA_STATION, orders: [order_in_progress] }

// ---------------------------------------------------------------------------
// Contracts: BuybackContractsTable, FreightContractsTable
// ---------------------------------------------------------------------------
const date_from_now = (ms: number) => new Date(Date.now() + ms)

const buyback = (id: number, over: Partial<BuybackContract>): BuybackContract => ({
    contract_id: 190_000_000 + id,
    status: 'outstanding',
    location_name: 'Amamake - Rattini Tribe Freeport',
    volume: 12_400,
    price: 184_500_000,
    title: '',
    date_issued: date_from_now(-3 * HOUR),
    date_completed: null,
    issuer_id: kel.id,
    issuer_character_name: kel.name,
    acceptor_id: null,
    acceptor_character_name: null,
    updated_at: date_from_now(-HOUR),
    ...over,
})

export const buyback_mixed: BuybackContract[] = [
    buyback(1, { price: 184_500_000, volume: 12_400 }),
    buyback(2, {
        status: 'in_progress',
        issuer_id: rattini.id,
        issuer_character_name: rattini.name,
        price: 2_310_000_000,
        volume: 88_900,
        title: 'Hurricane Fleet Issue hulls and fits',
        date_issued: date_from_now(-1 * DAY),
        acceptor_id: amamake.id,
        acceptor_character_name: amamake.name,
    }),
    buyback(3, {
        status: 'finished',
        issuer_id: hek.id,
        issuer_character_name: hek.name,
        location_name: 'Rens VI - Moon 8 - Brutor Tribe Treasury',
        price: 740_250_000,
        volume: 31_050,
        title: 'https://my.minmatar.org/market/buyback/appraisal/9aK2p/',
        date_issued: date_from_now(-4 * DAY),
        date_completed: date_from_now(-4 * DAY + 7 * HOUR),
        acceptor_id: kel.id,
        acceptor_character_name: kel.name,
    }),
    buyback(4, {
        status: 'finished',
        issuer_id: null,
        issuer_character_name: null,
        price: 56_000_000,
        volume: 640,
        date_issued: date_from_now(-9 * DAY),
        date_completed: date_from_now(-9 * DAY + 26 * HOUR),
        acceptor_id: null,
        acceptor_character_name: 'Auga Hauler',
    }),
]

export const buyback_history: BuybackContract[] = Array.from({ length: 14 }, (_, index) => buyback(100 + index, {
    status: 'finished',
    issuer_id: builders[index % builders.length].id,
    issuer_character_name: builders[index % builders.length].name,
    location_name: [AMAMAKE_STATION, RENS_STATION, AUGA_STATION][index % 3].location_name,
    price: 40_000_000 + index * 63_000_000,
    volume: 1_200 + index * 4_300,
    title: index % 4 === 0 ? 'Fleet fits' : '',
    date_issued: date_from_now(-(index + 2) * DAY),
    date_completed: date_from_now(-(index + 2) * DAY + (3 + index) * HOUR),
    acceptor_id: kel.id,
    acceptor_character_name: kel.name,
}))

const freight = (id: number, over: Partial<FreightContract>): FreightContract => ({
    contract_id: 195_000_000 + id,
    status: 'outstanding',
    start_location_name: 'Jita IV - Moon 4 - Caldari Navy Assembly Plant',
    end_location_name: 'Amamake - Rattini Tribe Freeport',
    volume: 310_000,
    collateral: 2_500_000_000,
    reward: 38_000_000,
    date_issued: iso_from_now(-5 * HOUR),
    date_completed: null,
    issuer_id: kel.id,
    issuer_character_name: kel.name,
    completed_by_id: null,
    completed_by_character_name: null,
    updated_at: iso_from_now(-HOUR),
    ...over,
})

export const freight_mixed: FreightContract[] = [
    freight(1, {}),
    freight(2, {
        status: 'in_progress',
        issuer_id: rattini.id,
        issuer_character_name: rattini.name,
        volume: 118_000,
        collateral: 900_000_000,
        reward: 14_500_000,
        start_location_name: 'Rens VI - Moon 8 - Brutor Tribe Treasury',
        date_issued: iso_from_now(-1 * DAY),
        completed_by_id: auga.id,
        completed_by_character_name: auga.name,
    }),
    freight(3, {
        status: 'finished',
        issuer_id: hek.id,
        issuer_character_name: hek.name,
        end_location_name: 'Auga - Pulse Tech Citadel',
        volume: 12_500,
        collateral: 140_000_000,
        reward: 2_400_000,
        date_issued: iso_from_now(-3 * DAY),
        date_completed: iso_from_now(-3 * DAY + 20 * HOUR),
        completed_by_id: auga.id,
        completed_by_character_name: auga.name,
    }),
]

export const freight_history: FreightContract[] = Array.from({ length: 12 }, (_, index) => freight(100 + index, {
    status: 'finished',
    issuer_id: builders[index % builders.length].id,
    issuer_character_name: builders[index % builders.length].name,
    volume: 8_000 + index * 21_000,
    collateral: 100_000_000 + index * 180_000_000,
    reward: 1_800_000 + index * 3_100_000,
    date_issued: iso_from_now(-(index + 2) * DAY),
    date_completed: iso_from_now(-(index + 2) * DAY + (12 + index) * HOUR),
    completed_by_id: vard.id,
    completed_by_character_name: vard.name,
}))

// ---------------------------------------------------------------------------
// Products: ProductItem, ProductsList
// ---------------------------------------------------------------------------
const product = (over: Partial<Product> & Pick<Product, 'id' | 'type_id' | 'name' | 'strategy'>): Product => ({
    blueprint_or_reaction_type_id: null,
    character_producers: [],
    corporation_producers: [],
    supplied_for: [],
    supplies: [],
    volume: null,
    ...over,
})

export const product_final_hull: Product = product({
    id: 4002,
    type_id: 24702,
    name: 'Hurricane',
    strategy: 'produced',
    blueprint_or_reaction_type_id: 24703,
    volume: 15_000,
})

export const product_mineral: Product = product({
    id: 3001,
    type_id: TRITANIUM,
    name: 'Tritanium',
    strategy: 'harvested',
    volume: 0.01,
    supplied_for: [
        { id: 4001, type_id: 587, name: 'Rifter' },
        { id: 4002, type_id: 24702, name: 'Hurricane' },
        { id: 4003, type_id: 11371, name: 'Wolf' },
    ],
})

export const product_imported_many_parents: Product = product({
    id: 3004,
    type_id: ISOGEN,
    name: 'Isogen',
    strategy: 'imported',
    volume: 0.01,
    supplied_for: [
        { id: 4001, type_id: 587, name: 'Rifter' },
        { id: 4002, type_id: 24702, name: 'Hurricane' },
        { id: 4003, type_id: 11371, name: 'Wolf' },
        { id: 4006, type_id: 622, name: 'Stabber' },
        { id: 4007, type_id: 16231, name: 'Cyclone' },
        { id: 4008, type_id: 12015, name: 'Muninn' },
        { id: 4009, type_id: 11999, name: 'Vagabond' },
        { id: 4010, type_id: 629, name: 'Rupture' },
    ],
})

export const products_list: Product[] = [
    product_final_hull,
    product({ id: 4001, type_id: 587, name: 'Rifter', strategy: 'produced', blueprint_or_reaction_type_id: 691, supplied_for: [{ id: 4003, type_id: 11371, name: 'Wolf' }] }),
    product({ id: 4003, type_id: 11371, name: 'Wolf', strategy: 'produced', blueprint_or_reaction_type_id: 11372 }),
    product({ id: 4006, type_id: 622, name: 'Stabber', strategy: 'produced', blueprint_or_reaction_type_id: 692 }),
    product_mineral,
    product({ id: 3002, type_id: PYERITE, name: 'Pyerite', strategy: 'harvested', supplied_for: [{ id: 4001, type_id: 587, name: 'Rifter' }, { id: 4002, type_id: 24702, name: 'Hurricane' }] }),
    product({ id: 3003, type_id: MEXALLON, name: 'Mexallon', strategy: 'produced', supplied_for: [{ id: 4002, type_id: 24702, name: 'Hurricane' }] }),
    product_imported_many_parents,
    product({ id: 3005, type_id: NOCXIUM, name: 'Nocxium', strategy: 'imported', supplied_for: [{ id: 4002, type_id: 24702, name: 'Hurricane' }] }),
]

// ---------------------------------------------------------------------------
// Cargo: CargoHold
// ---------------------------------------------------------------------------
export const cargo_fleet_fit: CargoItem[] = [
    { id: 2889, name: '200mm AutoCannon II', amount: 6 },
    { id: 519, name: 'Gyrostabilizer II', amount: 4 },
    { id: 2048, name: 'Damage Control II', amount: 2 },
    { id: 440, name: '5MN Microwarpdrive II', amount: 2 },
    { id: 448, name: 'Warp Scrambler II', amount: 3 },
    { id: 28668, name: 'Nanite Repair Paste', amount: 150 },
]
export const cargo_single: CargoItem[] = [{ id: 28668, name: 'Nanite Repair Paste', amount: 300 }]
export const cargo_no_amounts: CargoItem[] = [
    { id: 28668, name: 'Nanite Repair Paste' },
    { id: 587, name: 'Rifter' },
]
