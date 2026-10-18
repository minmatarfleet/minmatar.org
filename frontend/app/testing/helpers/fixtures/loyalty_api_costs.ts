import type { LoyaltyOffer, LoyaltyOfferConversionCosts } from '@dtypes/api.minmatar.org'

/*
 * What the backend serves as LoyaltyOffer.conversion_costs
 * (industry.helpers.plan_costing.lp_offer_side_costs) with today's defaults:
 * Accounting V sales tax and Red Frog freight on revenue. Test fixtures only;
 * loyalty_conversion_breakdown.test.ts pins this against real backend output.
 */
const SALES_TAX_RATE = 0.0337
const RED_FROG_RATE = 45_000_000 / 1_500_000_000

export function api_side_costs(
    lp_cost: number,
    quantity: number,
    market_price: number | null,
    input_freight_isk: number | null,
): LoyaltyOfferConversionCosts {
    const per_lp = (amount: number | null) => amount == null || lp_cost <= 0 ? null : amount / lp_cost
    const revenue = market_price == null ? null : market_price * Math.max(quantity, 1)
    return {
        sales_tax_isk_per_lp: per_lp(revenue == null ? null : Math.ceil(SALES_TAX_RATE * revenue)),
        input_freight_isk_per_lp: per_lp(input_freight_isk),
        output_freight_isk_per_lp: per_lp(revenue == null ? null : revenue > 0 ? Math.ceil(RED_FROG_RATE * revenue) : 0),
    }
}

/** The offer as the API returns it: conversion_costs for every priced side. */
export function with_api_costs(offer: LoyaltyOffer): LoyaltyOffer {
    if (offer.conversion_costs !== undefined)
        return offer
    const sides = { sell: offer.jita_sell, buy: offer.jita_buy, avg_7d: offer.jita_avg_7d } as const
    const conversion_costs: NonNullable<LoyaltyOffer['conversion_costs']> = {}
    for (const [side, price] of Object.entries(sides) as Array<[keyof typeof sides, number | null]>) {
        if (price != null)
            conversion_costs[side] = api_side_costs(offer.lp_cost, offer.quantity, price, offer.input_freight_isk)
    }
    return { ...offer, conversion_costs }
}
