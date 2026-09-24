import type { AmamakeMarketIssue } from './types'
import {
    AMAMAKE,
    CATCHMENT,
    CATEGORIES,
    DAYS,
    EXTRACTED_AT,
    FREIGHT_ISK_PER_M3,
    FREIGHT_ROUTE_LABEL,
    HULLS,
    JITA_AS_OF,
    LOCATION_ID,
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
import { without_empty_class_buckets, without_skins_and_blueprints } from './sales_filters'

export const SLUG = 'yc128-08' as const
export const PERMALINK_PATH = `/amamake-market/${SLUG}/` as const
export const COVER_IMAGE = '/images/home-amamake-cover.jpg'

const n = (value: number) => value.toLocaleString('en-US')

export const YC128_08: AmamakeMarketIssue = {
    slug: SLUG,
    permalink_path: PERMALINK_PATH,
    cover_image: COVER_IMAGE,
    published_at: new Date('2026-08-31T00:00:00Z'),
    period_utc: '1–31 Aug 2026 UTC',
    previous_period_label: 'July',
    context_as_of: JITA_AS_OF ?? EXTRACTED_AT.slice(0, 10),

    sales: SALES_TOTALS,
    sales_vs: SALES_TOTALS_VS,
    days: DAYS,
    weeks: WEEKS,
    weeks_dek: 'What moved through the Amamake keepstar this month, by class and by day.',
    categories: CATEGORIES.filter((row) => row.name !== 'Other' || without_skins_and_blueprints(TOP_TYPES_BY_CLASS.Other ?? []).length > 0),

    top_types: {
        rows: without_skins_and_blueprints(TOP_TYPES),
        by_class: without_empty_class_buckets(TOP_TYPES_BY_CLASS),
        dek: 'Biggest tickets on the book.',
    },

    hulls: {
        rows: HULLS,
        dek: 'What we sold here versus what died in the warzone.',
    },

    catchment: {
        amamake: AMAMAKE,
        warzone: WARZONE,
        rows: CATCHMENT,
        regions: REGIONS,
        pipe: PIPE,
        dek: 'Loudest systems this month.',
    },

    margins: {
        rows: without_skins_and_blueprints(MARGINS),
        dek: 'Volume that still pays after Jita and the hauler.',
        jita_as_of: JITA_AS_OF,
    },

    volume: {
        dek: 'Everything that moved. Markup still vs Jita after freight.',
        location_id: LOCATION_ID,
        year: 2026,
        month: 8,
    },

    get_involved: {
        dek: 'Pick types, haul them in on alliance freight, list them. Cheaper than PushX.',
        steps: [
            {
                title: 'Find the holes',
                text: 'Market ops shows demand, coverage, and gaps on the keepstar book. Last month\'s movers are in All Items Sold above.',
                href: '/market/ops/sell_orders/',
                label: 'Coverage and gaps',
            },
            {
                title: 'Haul it in',
                text: `Alliance freight is ${FREIGHT_ROUTE_LABEL} at ${n(FREIGHT_ISK_PER_M3)} ISK/m³. PushX and Red Frog charge more for the same jump.`,
                href: '/market/freight/calculator/',
                label: 'Freight service',
            },
            {
                title: 'List it',
                text: 'Park the stack on the freeport. If it still beats Jita after freight, it sells.',
                href: '/market/ops/',
                label: 'Live book',
            },
        ],
        actions: [
            { href: '/market/freight/calculator/', label: 'Freight calculator' },
            { href: '/market/ops/sell_orders/', label: 'Coverage and gaps' },
        ],
    },

    methodology: [
        {
            label: 'Orders',
            text: 'CCP does not post structure transactions. We snapshot the Amamake sell book about every fifteen minutes. A drop on an order counts as an order at that price. ISK is quantity times price, UTC month. Relists and cancels do not count, so every total is a floor. Empty columns on the day strip mean no snapshots.',
        },
        {
            label: 'Profit',
            text: `Per type: (Amamake fill average − Forge Jita guide − freight per unit) × units. Freight is the alliance ${FREIGHT_ROUTE_LABEL} rate: ${n(FREIGHT_ISK_PER_M3)} ISK/m³ × SDE packaged volume (volume only; the route's 1.5% collateral is omitted because these orders have none). Types with no Forge Jita average are excluded from the total, not treated as 0. August is ${SALES_TOTALS.profit_label} across ${n(SALES_TOTALS.profit_types)} priced types (${n(SALES_TOTALS.profit_unpriced_types)} omitted). Jita averages are dated ${JITA_AS_OF ?? 'month end'}.`,
        },
        {
            label: 'Month over month',
            text: 'Same number versus last calendar month, same snapshot feed. Profit uses that month\'s Jita guide the same way.',
        },
        {
            label: 'Markup',
            text: `Top Items Sold and Sell orders by class: volume-weighted fill average versus the Forge Jita guide (${JITA_AS_OF ?? 'month end'}), as a percent over Jita. No Jita history is an em-dash, not 0%. All Items Sold markup also knocks off freight.`,
        },
        {
            label: 'SKINs and blueprints',
            text: 'SKINs and BPO/BPC are off Top Items Sold, class chips, and All Items Sold. Month ISK still counts the whole book.',
        },
        {
            label: 'All Items Sold',
            text: `Paginated catalog of every non-SKIN/BP type that moved this month (5 per page), ranked by ISK. Markup and Extra ISK are Amamake fill average minus Jita minus ${n(FREIGHT_ISK_PER_M3)} ISK/m³ freight. Anonymous visitors get a small browse budget; more flips need login. Jita as of ${JITA_AS_OF ?? 'month end'}.`,
        },
        {
            label: 'Demand',
            text: 'Sold at the keepstar versus hulls that died in FW space. Capsules out. Ratio is sold in Amamake per warzone loss.',
        },
        {
            label: 'Destruction',
            text: `${WARZONE.systems} FW systems, capsules and NPC-only mails out, same zKill pass as the Frontline report. Holder mark is live ESI. Heimatar pipe (${PIPE.label}) is ${PIPE.share}% of those ships.`,
        },
    ],
}
