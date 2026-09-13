import type { AmamakeMarketIssue, MarketStat } from './types'
import {
    AMAMAKE,
    CAPITAL_SPLIT,
    CATCHMENT,
    CATEGORIES,
    CONTRACT_HULLS,
    CONTRACTS,
    DAYS,
    EXTRACTED_AT,
    FREIGHT_ISK_PER_M3,
    FREIGHT_ROUTE_LABEL,
    HUB_HEALTH,
    HULLS,
    HULLS_LOST_TOTAL,
    HULLS_SOLD_TOTAL,
    JITA_AS_OF,
    MARGINS,
    PIPE,
    REGIONS,
    SALES_TOTALS,
    SALES_TOTALS_VS,
    TOP_TYPES,
    TOP_TYPES_BY_CLASS,
    WARZONE,
    WEEKS,
} from './yc128-08-boards'

export const SLUG = 'yc128-08' as const
export const PERMALINK_PATH = `/amamake-market/${SLUG}/` as const
export const COVER_IMAGE = '/images/home-amamake-cover.jpg'

const n = (value: number) => value.toLocaleString('en-US')
const isk = (value: number) => {
    if (value >= 1_000_000_000_000) return `${(value / 1_000_000_000_000).toFixed(2)}T`
    if (value >= 100_000_000_000) return `${Math.round(value / 1_000_000_000)}B`
    if (value >= 1_000_000_000) return `${(value / 1_000_000_000).toFixed(2)}B`
    return `${(value / 1_000_000).toFixed(0)}M`
}
const day = (date: string) => {
    const d = new Date(`${date}T00:00:00Z`)
    return `${d.getUTCDate()} ${d.toLocaleString('en-US', { month: 'short', timeZone: 'UTC' })}`
}
const pct_word = (pct: number | null) =>
    pct === null ? 'with no July baseline' : pct >= 0 ? `up ${pct}% on July` : `down ${Math.abs(pct)}% on July`

const category = (name: string) => CATEGORIES.find((row) => row.name === name)
const kamela = CAPITAL_SPLIT.find((row) => row.system === 'Kamela')

const shelf_stats: MarketStat[] = []
if (HUB_HEALTH?.sell_orders_isk) {
    shelf_stats.push({ label: 'On sell orders', value: isk(HUB_HEALTH.sell_orders_isk), note: 'live book, all sellers' })
}
if (HUB_HEALTH?.contracts_isk) {
    shelf_stats.push({ label: 'On public contracts', value: isk(HUB_HEALTH.contracts_isk), note: 'fitted hulls, live' })
}
if (HUB_HEALTH?.sell_orders_health_pct != null) {
    shelf_stats.push({ label: 'Sells within markup of Jita', value: `${Math.round(HUB_HEALTH.sell_orders_health_pct)}%`, note: 'tracked doctrine types' })
}
if (HUB_HEALTH?.contracts_health_pct != null) {
    shelf_stats.push({ label: 'Doctrine contract coverage', value: `${Math.round(HUB_HEALTH.contracts_health_pct)}%` })
}

export const YC128_08: AmamakeMarketIssue = {
    slug: SLUG,
    permalink_path: PERMALINK_PATH,
    cover_image: COVER_IMAGE,
    published_at: new Date('2026-08-31T00:00:00Z'),
    period_utc: '1–31 Aug 2026 UTC',
    previous_period_label: 'July',
    context_as_of: JITA_AS_OF ?? EXTRACTED_AT.slice(0, 10),
    headline: 'Kamela ate capitals. Amamake sold destroyers.',
    opening: [
        'Hello sales tax enjoyers. This structure is still sixth on Fuzzwork by sell orders, behind Jita, Amarr, Dodixie, Hek, and Rens. CCP does not publish structure transactions; we watch the order book move about every fifteen minutes and treat every total on this page as a floor. Amarr dock here. Gallente and Caldari hulls sell here. This is a freeport on the warzone, not an alliance ledger.',
        `${SALES_TOTALS.isk_label} ISK moved through the book in August across ${n(SALES_TOTALS.fills)} inferred fills and ${n(SALES_TOTALS.types)} types, ${pct_word(SALES_TOTALS_VS.isk_pct)}. Money moved in ${CATEGORIES[0]?.name.toLowerCase()} (${CATEGORIES[0]?.isk_label}) and ${CATEGORIES[1]?.name.toLowerCase()} (${CATEGORIES[1]?.isk_label}); charges were ${category('Charges')?.isk_label ?? '—'} and ${n(category('Charges')?.units ?? 0)} units, which is the plexing ammo. The warzone around the shop lost ${n(WARZONE.ships)} ships and ${WARZONE.isk_label} ISK. Amamake was ${AMAMAKE.share_of_warzone}% of those ships.`,
        `Kamela ate ${kamela?.capital_ships ?? 0} capitals while this undock ate Typhoons. ${day(AMAMAKE.loudest_day.date)} was a local meat grinder, not a region-wide node.`,
    ],

    sales: SALES_TOTALS,
    sales_vs: SALES_TOTALS_VS,
    days: DAYS,
    weeks: WEEKS,
    weeks_dek:
        'A high level overview of the items that sold in the Amamake freeport keepstar, broken down by category and timeline.',
    categories: CATEGORIES,
    categories_dek: 'Sell-order ISK by class, inferred fills at the freeport. Month-over-month ISK, fills, units, and average markup versus Jita.',

    top_types: {
        rows: TOP_TYPES,
        by_class: TOP_TYPES_BY_CLASS,
        dek: 'The top items sold for each category. Markup is included so that you can gauge how much profit traders made on them.',
    },

    hulls: {
        rows: HULLS,
        dek: 'Hulls sold in Amamake versus lost in the warzone, and the systems around the shop that feed the book.',
        footnote: `August counts. Sells: inferred fills at the freeport. Losses: killmails in the Amarr–Minmatar warzone, capsules excluded. Ranked by sold plus lost; across every hull type ${n(HULLS_SOLD_TOTAL)} were sold here and ${n(HULLS_LOST_TOTAL)} were lost in the warzone.`,
    },

    catchment: {
        amamake: AMAMAKE,
        warzone: WARZONE,
        rows: CATCHMENT,
        regions: REGIONS,
        pipe: PIPE,
        dek: [
            `We watch ${WARZONE.systems} Amarr–Minmatar systems. Amamake is the shop and a pipe, so it will usually lead. The Heimatar run (${PIPE.label}) lost ${n(PIPE.ships)} ships this month, ${PIPE.share}% of the warzone. Kourmonen is still the volume system in The Bleak Lands. About ${n(AMAMAKE.unique_characters)} characters showed up on Amamake killmails. That is whoever flew the pipe, not a corporation.`,
            'Occupancy is a snapshot, not a monthly average. Amamake itself was Minmatar-held and quiet: dock, buy, leave. The loud systems were the ones being taken. Shop in the quiet ones. Plex in the loud ones.',
        ],
        footnote: `Ships destroyed, August 2026, ${WARZONE.systems} monitored systems, capsules and NPC-only kills removed, from the same zKillboard pass as the Warzone Report. Holder marks are the live ESI occupier. Capital ISK is the share of a system's destroyed ISK that was capital hulls.`,
    },

    contracts: CONTRACTS
        ? {
            totals: CONTRACTS,
            rows: CONTRACT_HULLS,
            dek: `Finished item-exchange contracts at the freeport, grouped by hull. ${n(CONTRACTS.count)} contracts for ${CONTRACTS.isk_label}, ${pct_word(CONTRACTS.count > 0 && CONTRACTS.count - CONTRACTS.count_vs > 0 ? Math.round((CONTRACTS.count_vs / (CONTRACTS.count - CONTRACTS.count_vs)) * 100) : null)}. ${n(CONTRACTS.unmatched)} had no matching doctrine fit and stay in the total only.`,
            footnote: `Finished public and private item-exchange contracts completed at the Amamake structure in August. ISK is the contract price. Ranked by ISK among hulls we could match to a doctrine fit (${n(CONTRACTS.matched)} of ${n(CONTRACTS.count)}). Unmatched titles are in the month total, not the table.`,
        }
        : null,

    margins: {
        rows: MARGINS,
        dek: 'High volume items that still offer great profit margins.',
        footnote: `Mean inferred fill price versus the Forge daily average on ${JITA_AS_OF ?? 'month end'}, plus 450 ISK/m³ on SDE packaged volume. Types need at least 25 inferred fills and 25 units (August participation floor — thin books cook if extra seeders pile in) and a 5% spread after freight. Ranked by extra ISK, not fattest percent. Blueprints excluded.`,
        jita_as_of: JITA_AS_OF,
    },

    import_vs_local: {
        dek: [
            'Same goal as March: things that actually move, under 20% of Jita after freight. Jita to Amamake is 450 ISK/m³ packaged. Fleet Issue destroyers are already here. Typhoons are not. Hail and Republic Fleet EMP print Jita, so that is a pickup, not a jump freighter.',
        ],
        table: {
            headers: ['Type', 'Amamake', 'Jita', 'Freight in', 'Call'],
            rows: [
                { cells: ['Thrasher Fleet Issue', '16.8M', '17.5M', '1.1M', 'Skip'], tone: 'success' },
                { cells: ['Hurricane Fleet Issue', '122.8M', '124.2M', '6.8M', 'Skip'], tone: 'success' },
                { cells: ['Hecate', '83.6M', '85.4M', '2.3M', 'Skip'], tone: 'success' },
                { cells: ['Stabber Fleet Issue', '40.1M', '40.1M', '4.5M', 'Skip'], tone: 'success' },
                { cells: ['Typhoon', '195.0M', '170.5M', '22.5M', 'Haul'], tone: 'info' },
                { cells: ['Nanite Repair Paste', '28.2k', '28.1k', '~0', 'Even'] },
                { cells: ['Hail M / RF EMP S', 'Jita print', 'Jita print', '~0', 'Pickup'] },
            ],
            footnote:
                'Lowest Amamake sell versus the Jita average on 31 Aug, after 450 ISK/m³ freight (destroyer 2,500 m³, tactical destroyer 5,000, cruiser 10,000, battlecruiser 15,000, battleship 50,000). Skip: local is already cheaper. Haul: Jita plus freight still wins. Hand-collected month-end snapshot.',
        },
    },

    shelf: {
        dek: [
            'Nanite around 28,000 with hundreds of thousands on the shelf. Hail is a pickup. Thrasher Fleet Issue under 17 million. Typhoon around 195 million and thin. We do not list which fittings are empty; the public sell-orders page already shows what is low.',
            'You can undock a fitted destroyer without a hauler alt. Travel to Amamake, buy the ship, pick a small complex off the Agency window. The book does not check your militia.',
        ],
        stats: shelf_stats,
        actions: [
            { href: '/market/ops/sell_orders/', label: 'Sell orders' },
            { href: 'https://market.fuzzwork.co.uk/station/1022167642188/', label: 'Fuzzwork station book' },
            { href: `https://zkillboard.com/system/${AMAMAKE.system_id}/`, label: 'zKill Amamake' },
            { href: 'https://www.reddit.com/r/Eve/comments/1rhy941/how_minmatar_fleet_uses_esi_to_support_multiple/', label: 'How we run the markets (Mar YC128)' },
        ],
    },

    get_involved: {
        steps: [
            {
                title: 'Buy here',
                text: 'Every doctrine hull and fit is on the shelf or on contract. Check the public book before you haul anything from Jita.',
                href: '/market/ops/sell_orders/',
                label: 'Browse the sell orders',
            },
            {
                title: 'Sell here',
                text: 'List at or under Jita plus freight and it moves. Fleet Issue destroyers, navy cruisers, paste, and ammo cleared all month; battleships did not.',
                href: '/market/ops/contracts/',
                label: 'Doctrine contracts',
            },
            {
                title: 'Build here',
                text: 'Faction warfare level 5 gives the −50% index rebate. Refine in Amo, react anywhere but Auner, and job the hulls in the died-vs-sold table that sold under Jita.',
                href: '/industry/',
                label: 'Industry hub',
            },
        ],
        actions: [{ href: 'https://discord.com/invite/3hZfahmkFx', label: 'Join Militia Discord' }],
        featured_guides: ['navy-destroyer-metagame', 'navy-frigate-guide'],
    },

    methodology: [
        {
            label: 'Inferred fills',
            text: 'CCP does not publish structure transactions. Minmatar Fleet snapshots the Amamake sell book about every fifteen minutes and records each drop in an order as a fill at that order\'s price. ISK sold is quantity times fill price, summed over the calendar month (UTC). Buy orders, relists and cancelled orders are not counted, so every total is a floor.',
        },
        {
            label: 'Inferred profit',
            text: `Per type-month: (Amamake fill average − Forge Jita guide − freight per unit) × units. Freight is the alliance ${FREIGHT_ROUTE_LABEL} rate from the freight calculator: ${n(FREIGHT_ISK_PER_M3)} ISK/m³ × SDE packaged volume (volume charge only; the route also has 1.5% collateral, which is omitted because inferred fills have no collateral). Types with no Forge Jita average are excluded from the total, not treated as 0. August is ${SALES_TOTALS.profit_label} across ${n(SALES_TOTALS.profit_types)} priced types (${n(SALES_TOTALS.profit_unpriced_types)} omitted). Jita averages are dated ${JITA_AS_OF ?? 'month end'}.`,
        },
        {
            label: 'Month over month',
            text: 'Deltas compare the same measure against the prior calendar month from the same snapshot feed. Inferred profit uses that month\'s Forge Jita guide the same way.',
        },
        {
            label: 'Market Capture',
            text: 'Hull losses are killmails across the Amarr–Minmatar faction-warfare systems, capsules excluded, matched by type to inferred sells of the same hull at the Amamake structure. The ratio is sold in Amamake per warzone loss.',
        },
        {
            label: 'Destruction',
            text: 'Every ship kill in the Amarr–Minmatar faction-warfare systems for the month, from zKillboard, with capsules and NPC-only kills removed. Identical to the Warzone Report for the same month.',
        },
        {
            label: 'Contracts',
            text: 'Finished item-exchange contracts at the Amamake structure, priced as listed. Hull rows are doctrine fits we could match; unmatched contracts stay in the month total.',
        },
        {
            label: 'Items worth seeding',
            text: `Extra ISK is the inferred fill average minus the Forge Jita guide minus 450 ISK/m³ freight, times units. Jita averages are dated ${JITA_AS_OF ?? 'month end'}. Types need at least 25 inferred fills and 25 units (August 2026 participation floor: among 5%-over-Jita types, median fills were 29 and the units quartile was 21). A spread under 5% after freight, no Jita history, or an SDE blueprint is omitted. Ranked by extra ISK, not fattest percent.`,
        },
        {
            label: 'Markup',
            text: `Markup on What sold and Sell orders by class is the volume-weighted inferred fill average versus the Forge daily Jita guide (${JITA_AS_OF ?? 'month end'}), as a percent over Jita. Types and classes with no Forge history show an em-dash, not 0%. This is not the Items worth seeding spread, which also subtracts freight.`,
        },
        {
            label: 'Live context',
            text: `Hub-health figures are a live snapshot from the Minmatar Fleet API. The import table is a hand-collected month-end snapshot of the live book, not the inferred-fill averages above.`,
        },
        {
            label: 'Not shown',
            text: 'No operator names, no per-seller volumes, no empty-fitting list, and no live hull depth. The public sell-orders page shows what is low.',
        },
    ],
}
