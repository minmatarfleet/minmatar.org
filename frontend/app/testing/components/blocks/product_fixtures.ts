import type { Product, ProductBuild, ProductInsights, ProductWeek } from "@dtypes/api.minmatar.org";

const DAY = 24 * 60 * 60 * 1000;

export const days_ago = (days: number) => new Date(Date.now() - days * DAY).toISOString();

// Thirteen Monday-ish week starts ending this week, oldest first.
export const weeks = (rows: Partial<ProductWeek>[] = []): ProductWeek[] =>
    Array.from({ length: 13 }, (_, index) => ({
        week_start: days_ago((12 - index) * 7 + 3),
        built: 0,
        sold: 0,
        lost: 0,
        ...(rows[index] ?? {}),
    }));

export const insights = (overrides: Partial<ProductInsights> = {}): ProductInsights => ({
    ready: true,
    generated_at: days_ago(0),
    is_ship: true,
    window_days: 90,
    recent_days: 30,
    unit_price: 167_000_000,
    built: {
        units_30d: 6,
        units_90d: 24,
        jobs_90d: 10,
        builders_90d: 3,
        running_units: 4,
        running_jobs: 2,
        last_built_at: days_ago(2),
    },
    builders: [
        { character_id: 1, character_name: "Barret Smythe", units: 18, jobs: 6, last_built_at: days_ago(2) },
        { character_id: 2, character_name: "Entitiez", units: 6, jobs: 4, last_built_at: days_ago(9) },
    ],
    corporations: [],
    running: [
        { character_id: 1, character_name: "Barret Smythe", corporation_name: "Ballah Inc.", units: 3, ends_at: new Date(Date.now() + DAY).toISOString() },
    ],
    orders: {
        open_orders: 2,
        open_units: 6,
        open_assigned_units: 4,
        open_delivered_units: 1,
        ordered_units_90d: 9,
        recent: [
            {
                order_id: 11, public_short_code: "K7Q2", character_id: 1, character_name: "Doctrine stock",
                created_at: days_ago(5), needed_by: days_ago(-7).slice(0, 10), fulfilled_at: null,
                quantity: 4, assigned: 2, delivered: 1,
            },
            {
                order_id: 12, public_short_code: "M3XA", character_id: 2, character_name: "Armor SIG",
                created_at: days_ago(3), needed_by: null, fulfilled_at: null,
                quantity: 2, assigned: 2, delivered: 0,
            },
        ],
    },
    sales: {
        market_units_30d: 1,
        market_units_90d: 3,
        contract_units_30d: 1,
        contract_units_90d: 2,
        listed_units: 2,
        lowest_listed_price: 179_000_000,
        outstanding_contracts: 1,
        locations: [{ location_name: "Amamake Freeport", units: 1 }],
    },
    hangars: {
        units: 22,
        pilots: 19,
        locations: [{ location_name: "Amamake Freeport", units: 11 }, { location_name: "Staging", units: 6 }],
    },
    losses: {
        units_30d: 35,
        units_90d: 70,
        recent: [],
        fights: [
            { solar_system_id: 30002537, solar_system_name: "Amamake", started_at: days_ago(7), ended_at: days_ago(7), units: 30, killmail_id: 139068329 },
            { solar_system_id: 30005000, solar_system_name: "Ahbazon", started_at: days_ago(77), ended_at: days_ago(77), units: 20, killmail_id: 137410154 },
        ],
        small_fight_units: 10,
        small_fight_systems: 7,
    },
    weekly: weeks([{}, { lost: 21 }, { built: 3 }, {}, {}, {}, {}, {}, {}, {}, {}, { built: 2, lost: 32, sold: 1 }, {}]),
    ...overrides,
});

export const product = (overrides: Partial<Product> = {}): Product => ({
    id: 174,
    type_id: 24692,
    name: "Abaddon",
    strategy: "produced",
    volume: 50000,
    blueprint_or_reaction_type_id: 24693,
    supplied_for: [],
    supplies: [],
    character_producers: [],
    corporation_producers: [],
    ...overrides,
});

export const build = (overrides: Partial<ProductBuild> = {}): ProductBuild => ({
    product_id: 174,
    type_id: 24692,
    blueprint_type_id: 24693,
    activity: "manufacturing",
    products_per_run: 1,
    time_seconds: 108000,
    sell_price: 167_000_000,
    material_cost: 150_000_000,
    margin: 17_000_000,
    prices_complete: true,
    materials: [
        { type_id: 34, name: "Tritanium", quantity: 9_000_000, unit_price: 3.64, line_cost: 32_760_000, strategy: "harvested", industry_product_id: 92 },
        { type_id: 57479, name: "Core Temperature Regulator", quantity: 3, unit_price: 3_352_945, line_cost: 10_058_835, strategy: null, industry_product_id: null },
    ],
    ...overrides,
});
