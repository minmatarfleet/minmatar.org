import type { LoyaltyOffer } from '@dtypes/api.minmatar.org'
import {
    loyalty_conversion_breakdown,
    net_isk_per_lp_for_cost_options,
    type LoyaltyConversionCostOptions,
} from '@helpers/loyalty_conversion_breakdown'

export type LoyaltyOffersSide = 'sell' | 'buy' | 'avg_7d'

/** Tribal Liberation Force — default currency on the public offers page. */
export const TLIB_CORP_ID = 1000182

export const DEFAULT_LOYALTY_OFFERS_SIDE: LoyaltyOffersSide = 'buy'

/** Default: net conversion includes Red Frog input/output freight. */
export const DEFAULT_INCLUDE_FREIGHT = true

/** Default: net conversion includes Accounting V sales tax. */
export const DEFAULT_INCLUDE_SALES_TAX = true

/** Default query params for /industry/loyalty/offers/ and filter reset. */
export const DEFAULT_LOYALTY_OFFERS_PARAMS: Record<string, string> = {
    currency: String(TLIB_CORP_ID),
    exclude_tags: '1',
    exclude_blueprints: '1',
    exclude_useless_offers: '1',
    include_freight: '1',
    include_sales_tax: '1',
    side: DEFAULT_LOYALTY_OFFERS_SIDE,
    ordering: `-conversion_${DEFAULT_LOYALTY_OFFERS_SIDE}`,
}

/**
 * Categories folded into the "Exclude useless offers" chip (packages, chips,
 * skins). When that chip is on, these API flags are also set.
 */
export const USELESS_OFFER_EXCLUDE_BUNDLE = [
    'exclude_supply_packages',
    'exclude_chips',
    'exclude_skins',
] as const

/** Expand exclude_useless_offers into its bundled category excludes. */
export function expand_useless_offer_excludes(
    exclude_useless_offers: string | undefined,
): Record<string, string> {
    if (exclude_useless_offers !== '1')
        return {}
    const out: Record<string, string> = { exclude_useless_offers: '1' }
    for (const key of USELESS_OFFER_EXCLUDE_BUNDLE)
        out[key] = '1'
    return out
}

/**
 * Toggle overrides for the useless chip (clears or sets the full bundle).
 * Undefined values delete keys from the current filter URL.
 */
export function useless_offer_exclude_toggle(
    enable: boolean,
): Record<string, string | undefined> {
    if (enable)
        return expand_useless_offer_excludes('1')
    const out: Record<string, string | undefined> = {
        exclude_useless_offers: undefined,
    }
    for (const key of USELESS_OFFER_EXCLUDE_BUNDLE)
        out[key] = undefined
    return out
}

/**
 * Share of weekly LP volume a single actor can typically take across the
 * filtered catalog without owning each item's book (~15–25% rule of thumb).
 */
export const STABLE_WEEKLY_CAPTURE_SHARE = 0.2

export interface LoyaltyOffersMetrics {
    average_isk_per_lp: number | null
    /** Sum of LP-equivalent 7d market volume across filtered offers. */
    weekly_total_volume: number
    /** Reasonable cash-out size: {@link STABLE_WEEKLY_CAPTURE_SHARE} of total. */
    weekly_stable_volume: number
}

export function resolve_conversion_cost_options(
    include_freight: boolean = DEFAULT_INCLUDE_FREIGHT,
    include_sales_tax: boolean = DEFAULT_INCLUDE_SALES_TAX,
): LoyaltyConversionCostOptions {
    return {
        include_freight,
        include_sales_tax,
    }
}

export function conversion_for_side(
    offer: LoyaltyOffer,
    side: LoyaltyOffersSide,
    include_freight: boolean = DEFAULT_INCLUDE_FREIGHT,
    include_sales_tax: boolean = DEFAULT_INCLUDE_SALES_TAX,
): number | null {
    const net_with_all_costs = side === 'buy'
        ? offer.conversion_isk_per_lp_buy
        : side === 'avg_7d'
            ? offer.conversion_isk_per_lp_avg_7d
            : offer.conversion_isk_per_lp_sell
    const options = resolve_conversion_cost_options(
        include_freight,
        include_sales_tax,
    )
    if (options.include_freight && options.include_sales_tax)
        return net_with_all_costs

    const breakdown = loyalty_conversion_breakdown({
        lp_cost: offer.lp_cost,
        quantity: offer.quantity,
        market_price: market_price_for_side(offer, side),
        input_cost_isk: offer.input_cost_isk,
        input_freight_isk: offer.input_freight_isk,
        isk_cost: offer.isk_cost,
        other_cost: offer.other_cost,
        net_isk_per_lp: net_with_all_costs,
    })
    return net_isk_per_lp_for_cost_options(
        net_with_all_costs,
        breakdown,
        options,
    )
}

export function market_price_for_side(
    offer: LoyaltyOffer,
    side: LoyaltyOffersSide,
): number | null {
    if (side === 'buy')
        return offer.jita_buy
    if (side === 'avg_7d')
        return offer.jita_avg_7d
    return offer.jita_sell
}

/**
 * Re-sort when freight/tax is excluded and ordering is by conversion — API
 * order still uses fully-netted rates.
 */
export function sort_loyalty_offers(
    offers: LoyaltyOffer[],
    ordering: string,
    side: LoyaltyOffersSide,
    include_freight: boolean = DEFAULT_INCLUDE_FREIGHT,
    include_sales_tax: boolean = DEFAULT_INCLUDE_SALES_TAX,
): LoyaltyOffer[] {
    if (include_freight && include_sales_tax)
        return offers

    const conversion_key = conversion_ordering_key(side)
    const descending = ordering.startsWith('-')
    const key = descending ? ordering.slice(1) : ordering
    if (key !== conversion_key)
        return offers

    return [...offers].sort((a, b) => {
        const av = conversion_for_side(a, side, include_freight, include_sales_tax)
        const bv = conversion_for_side(b, side, include_freight, include_sales_tax)
        if (av == null && bv == null)
            return 0
        if (av == null)
            return 1
        if (bv == null)
            return -1
        return descending ? bv - av : av - bv
    })
}

export function conversion_ordering_key(side: LoyaltyOffersSide): string {
    if (side === 'buy')
        return 'conversion_buy'
    if (side === 'avg_7d')
        return 'conversion_avg_7d'
    return 'conversion_sell'
}

/** LP needed to cover market volume (matches row volume tooltips). */
export function offer_lp_for_volume(
    offer: LoyaltyOffer,
    volume: number | null | undefined,
): number {
    if (volume == null || volume <= 0)
        return 0
    const qty = offer.quantity || 1
    return Math.ceil(volume / qty) * offer.lp_cost
}

/** Weekly LP volume below this is treated as thin / dangerous liquidity. */
export const LOW_WEEKLY_LP_VOLUME_THRESHOLD = 1_000_000

export function offer_is_low_weekly_lp_volume(offer: LoyaltyOffer): boolean {
    return offer_lp_for_volume(offer, offer.volume_7d) < LOW_WEEKLY_LP_VOLUME_THRESHOLD
}

export function compute_loyalty_offers_metrics(
    offers: LoyaltyOffer[],
    side: LoyaltyOffersSide,
    include_freight: boolean = DEFAULT_INCLUDE_FREIGHT,
    include_sales_tax: boolean = DEFAULT_INCLUDE_SALES_TAX,
): LoyaltyOffersMetrics {
    let weekly_total_volume = 0
    let weighted_conversion = 0
    let weight_sum = 0

    for (const offer of offers) {
        const weekly_lp = offer_lp_for_volume(offer, offer.volume_7d)
        weekly_total_volume += weekly_lp

        const conversion = conversion_for_side(
            offer,
            side,
            include_freight,
            include_sales_tax,
        )
        if (conversion == null || weekly_lp <= 0)
            continue
        weighted_conversion += conversion * weekly_lp
        weight_sum += weekly_lp
    }

    return {
        average_isk_per_lp: weight_sum > 0
            ? weighted_conversion / weight_sum
            : null,
        weekly_total_volume,
        weekly_stable_volume: weekly_total_volume * STABLE_WEEKLY_CAPTURE_SHARE,
    }
}
