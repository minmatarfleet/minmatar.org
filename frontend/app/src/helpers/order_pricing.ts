import type { OrderLinePricing, OrderPriceBasis } from '@dtypes/api.minmatar.org'

export const ORDER_PRICE_BASES: OrderPriceBasis[] = ['jita_buy', 'jita_split', 'jita_sell', 'margin']
export const DEFAULT_PRICE_BASIS: OrderPriceBasis = 'jita_split'
export const DEFAULT_MARGIN_PERCENT = 5

export interface OrderLinePrice {
    basis:      OrderPriceBasis;
    margin:     number;
    price:      number;
    profit:     number;
    saving:     number | null;
}

export function parse_price_basis(value: string | null | undefined): OrderPriceBasis {
    return ORDER_PRICE_BASES.includes(value as OrderPriceBasis)
        ? value as OrderPriceBasis
        : DEFAULT_PRICE_BASIS
}

export function parse_margin(value: string | null | undefined): number {
    const margin = parseFloat(value ?? '')
    return Number.isFinite(margin) ? margin : DEFAULT_MARGIN_PERCENT
}

export function preset_price(pricing: OrderLinePricing, basis: OrderPriceBasis): number | null {
    if (basis === 'margin')
        return null
    return pricing[basis]
}

/** A preset is offered only when it covers the build cost. */
export function preset_available(pricing: OrderLinePricing, basis: OrderPriceBasis): boolean {
    if (basis === 'margin')
        return true
    const price = preset_price(pricing, basis)
    return price !== null && price >= pricing.build_cost_per_unit
}

/**
 * Mirrors the backend's resolve_unit_price: never below the build cost.
 * A preset under it falls back to the build cost (a 0% margin).
 */
export function resolve_line_price(
    pricing: OrderLinePricing,
    basis: OrderPriceBasis,
    margin_percent: number,
): OrderLinePrice {
    const floor = pricing.build_cost_per_unit
    let price: number
    let margin: number

    if (basis !== 'margin' && preset_available(pricing, basis)) {
        price = preset_price(pricing, basis) as number
        margin = floor > 0 ? Math.round((price - floor) / floor * 1000) / 10 : 0
    } else {
        if (basis !== 'margin')
            margin_percent = 0
        basis = 'margin'
        margin = Math.max(margin_percent, 0)
        price = Math.round(floor * (1 + margin / 100))
    }

    return {
        basis,
        margin,
        price,
        profit: price - floor,
        saving: pricing.jita_delivered === null ? null : pricing.jita_delivered - price,
    }
}
