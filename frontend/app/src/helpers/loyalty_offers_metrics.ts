import type { LoyaltyOffer } from '@dtypes/api.minmatar.org'

export type LoyaltyOffersSide = 'sell' | 'buy' | 'avg_7d'

export interface LoyaltyOffersMetrics {
    average_isk_per_lp: number | null
    weekly_lp_volume: number
    monthly_lp_volume: number
}

function conversion_for_side(
    offer: LoyaltyOffer,
    side: LoyaltyOffersSide,
): number | null {
    if (side === 'buy')
        return offer.conversion_isk_per_lp_buy
    if (side === 'avg_7d')
        return offer.conversion_isk_per_lp_avg_7d
    return offer.conversion_isk_per_lp_sell
}

/** LP needed to cover market volume (matches row volume tooltips). */
export function offer_lp_for_volume(
    offer: LoyaltyOffer,
    volume: number | null | undefined,
): number {
    if (volume == null || volume <= 0)
        return 0
    const qty = Math.max(offer.quantity || 1, 1)
    return Math.ceil(volume / qty) * offer.lp_cost
}

export function compute_loyalty_offers_metrics(
    offers: LoyaltyOffer[],
    side: LoyaltyOffersSide,
): LoyaltyOffersMetrics {
    let weekly_lp_volume = 0
    let monthly_lp_volume = 0
    let weighted_conversion = 0
    let weight_sum = 0

    for (const offer of offers) {
        const weekly_lp = offer_lp_for_volume(offer, offer.volume_7d)
        const monthly_lp = offer_lp_for_volume(offer, offer.volume_30d)
        weekly_lp_volume += weekly_lp
        monthly_lp_volume += monthly_lp

        const conversion = conversion_for_side(offer, side)
        if (conversion == null || weekly_lp <= 0)
            continue
        weighted_conversion += conversion * weekly_lp
        weight_sum += weekly_lp
    }

    return {
        average_isk_per_lp: weight_sum > 0
            ? weighted_conversion / weight_sum
            : null,
        weekly_lp_volume,
        monthly_lp_volume,
    }
}
