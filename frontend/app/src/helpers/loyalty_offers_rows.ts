import type { LoyaltyOffer } from '@dtypes/api.minmatar.org'
import { SHORT_AMOUNT, format_compact } from '@helpers/numbers'
import {
    conversion_for_side,
    conversion_ordering_key,
    market_price_for_side,
    offer_lp_for_volume,
    type LoyaltyOffersSide,
} from '@helpers/loyalty_offers_metrics'
import {
    loyalty_conversion_breakdown,
    resolve_input_cost_isk,
    type LoyaltyConversionCostOptions,
} from '@helpers/loyalty_conversion_breakdown'

/**
 * Per-row decision math for the LP store offers table: how much capital an
 * offer ties up, how much LP the market absorbs a week, and how deep that is.
 */

export type LoyaltyOfferDepth = 'thin' | 'steady' | 'deep'

/** Weekly LP below this is thin: one seller can swamp the book. */
export const THIN_WEEKLY_LP_MAX = 500_000

/** Weekly LP above this is deep: room for a real conversion run. */
export const DEEP_WEEKLY_LP_MIN = 5_000_000

/** Capital is quoted per this much LP converted. */
export const CAPITAL_LP_BASIS = 100_000

/** Local (frontend-computed) sort keys the API does not know about. */
export const LOCAL_OFFER_ORDERING_KEYS = ['capital_per_100k', 'weekly_lp'] as const

export type LocalOfferOrderingKey = typeof LOCAL_OFFER_ORDERING_KEYS[number]

/** LP the Jita market absorbs per week for this offer (7d volume / qty × LP). */
export function offer_weekly_lp(offer: LoyaltyOffer): number {
    return offer_lp_for_volume(offer, offer.volume_7d)
}

/** ISK tied up (store ISK + required items) per {@link CAPITAL_LP_BASIS} LP. */
export function offer_capital_per_100k_lp(offer: LoyaltyOffer): number | null {
    if (!offer.lp_cost || offer.lp_cost <= 0)
        return null
    return resolve_input_cost_isk(offer) / offer.lp_cost * CAPITAL_LP_BASIS
}

export function offer_depth(weekly_lp: number): LoyaltyOfferDepth {
    if (weekly_lp < THIN_WEEKLY_LP_MAX)
        return 'thin'
    if (weekly_lp > DEEP_WEEKLY_LP_MIN)
        return 'deep'
    return 'steady'
}

/**
 * Short figure for table cells: 113M, 14.9M, 600K, 950. One decimal below
 * 100 of a unit, none above, so columns stay three significant figures.
 */
export function format_short_amount(value: number | null | undefined): string {
    if (value == null || !Number.isFinite(value))
        return '—'
    if (value <= 0)
        return '0'
    return format_compact(value, SHORT_AMOUNT)
}

export interface LoyaltyOfferRequiredItem {
    name: string
    quantity: number
}

/** Parse "Cap Booster 400 x20, Some Chip x1" into names + quantities. */
export function parse_required_items(summary: string | null | undefined): LoyaltyOfferRequiredItem[] {
    const out: LoyaltyOfferRequiredItem[] = []
    for (const part of (summary || '').split(',')) {
        const trimmed = part.trim()
        if (!trimmed)
            continue
        const match = trimmed.match(/^(.*)\s+x(\d+)\s*$/i)
        if (!match) {
            out.push({ name: trimmed, quantity: 1 })
            continue
        }
        out.push({
            name: match[1].trim(),
            quantity: Number.parseInt(match[2], 10),
        })
    }
    return out
}

export interface LoyaltyOfferRecipe {
    lp_cost: number
    isk_cost: number
    items: Array<LoyaltyOfferRequiredItem & {
        /** False when the item pairs 1:1 with the offer's own quantity. */
        show_quantity: boolean
    }>
}

/** What the store asks for: LP, ISK and required items. */
export function offer_recipe(offer: LoyaltyOffer): LoyaltyOfferRecipe {
    const offer_qty = Math.max(offer.quantity || 1, 1)
    return {
        lp_cost: offer.lp_cost,
        isk_cost: offer.isk_cost || 0,
        items: parse_required_items(offer.required_items_summary).map((item) => ({
            ...item,
            show_quantity: item.quantity > 1 && item.quantity !== offer_qty,
        })),
    }
}

export interface LoyaltyOfferRowFigures {
    net_isk_per_lp: number | null
    capital_per_100k_lp: number | null
    weekly_lp: number
    depth: LoyaltyOfferDepth
}

export function offer_row_figures(
    offer: LoyaltyOffer,
    side: LoyaltyOffersSide,
    include_freight: boolean,
    include_sales_tax: boolean,
): LoyaltyOfferRowFigures {
    const weekly_lp = offer_weekly_lp(offer)
    return {
        net_isk_per_lp: conversion_for_side(offer, side, include_freight, include_sales_tax),
        capital_per_100k_lp: offer_capital_per_100k_lp(offer),
        weekly_lp,
        depth: offer_depth(weekly_lp),
    }
}

/**
 * Bar scale for the Net ISK/LP column: the best shown net, but kept between
 * 1.25× and 2× the buyback rate so one outlier does not flatten every bar.
 */
export function net_bar_scale(
    nets: Array<number | null | undefined>,
    buyback_isk_per_lp: number | null | undefined,
): number {
    let max_net = 0
    for (const net of nets) {
        if (net != null && Number.isFinite(net) && net > max_net)
            max_net = net
    }
    if (buyback_isk_per_lp != null && buyback_isk_per_lp > 0) {
        const floor = buyback_isk_per_lp * 1.25
        const cap = buyback_isk_per_lp * 2
        return Math.min(Math.max(max_net, floor), cap)
    }
    return max_net > 0 ? max_net : 1
}

/** 0–100 width for a value on a bar scaled to `scale`. */
export function bar_percent(value: number | null | undefined, scale: number): number {
    if (value == null || !Number.isFinite(value) || value <= 0 || scale <= 0)
        return 0
    return Math.min(100, value / scale * 100)
}

export interface DeepOffersSummary {
    count: number
    net_min: number | null
    net_max: number | null
    capital_min: number | null
    capital_max: number | null
}

/** Net ISK/LP and capital ranges across the deep offers only. */
export function summarize_deep_offers(rows: LoyaltyOfferRowFigures[]): DeepOffersSummary {
    const summary: DeepOffersSummary = {
        count: 0,
        net_min: null,
        net_max: null,
        capital_min: null,
        capital_max: null,
    }
    for (const row of rows) {
        if (row.depth !== 'deep')
            continue
        summary.count += 1
        if (row.net_isk_per_lp != null) {
            summary.net_min = summary.net_min == null
                ? row.net_isk_per_lp
                : Math.min(summary.net_min, row.net_isk_per_lp)
            summary.net_max = summary.net_max == null
                ? row.net_isk_per_lp
                : Math.max(summary.net_max, row.net_isk_per_lp)
        }
        if (row.capital_per_100k_lp != null) {
            summary.capital_min = summary.capital_min == null
                ? row.capital_per_100k_lp
                : Math.min(summary.capital_min, row.capital_per_100k_lp)
            summary.capital_max = summary.capital_max == null
                ? row.capital_per_100k_lp
                : Math.max(summary.capital_max, row.capital_per_100k_lp)
        }
    }
    return summary
}

export function is_local_offer_ordering(ordering: string): boolean {
    const key = ordering.startsWith('-') ? ordering.slice(1) : ordering
    return (LOCAL_OFFER_ORDERING_KEYS as readonly string[]).includes(key)
}

/** The API cannot sort by local keys; ask it for its default instead. */
export function api_offer_ordering(ordering: string, side: LoyaltyOffersSide): string {
    if (!is_local_offer_ordering(ordering))
        return ordering
    return `-${conversion_ordering_key(side)}`
}

/** Sort by a local key (capital or weekly LP); other orderings pass through. */
export function sort_offers_by_local_key(
    offers: LoyaltyOffer[],
    ordering: string,
): LoyaltyOffer[] {
    if (!is_local_offer_ordering(ordering))
        return offers
    const descending = ordering.startsWith('-')
    const key = (descending ? ordering.slice(1) : ordering) as LocalOfferOrderingKey
    const value_of = (offer: LoyaltyOffer): number | null => key === 'weekly_lp'
        ? offer_weekly_lp(offer)
        : offer_capital_per_100k_lp(offer)
    return [...offers].sort((a, b) => {
        const av = value_of(a)
        const bv = value_of(b)
        if (av == null && bv == null)
            return 0
        if (av == null)
            return 1
        if (bv == null)
            return -1
        return descending ? bv - av : av - bv
    })
}

export type LoyaltyLpWaterfallKey =
    | 'store_isk'
    | 'required_items'
    | 'freight_in'
    | 'sales_tax'
    | 'freight_out'

export interface LoyaltyLpWaterfall {
    /** Jita value of the output per LP, before any cost. */
    gross_isk_per_lp: number | null
    /** Costs per LP, in the order they are paid. Zero rows are dropped. */
    costs: Array<{ key: LoyaltyLpWaterfallKey, isk_per_lp: number }>
    net_isk_per_lp: number | null
}

/**
 * "Where each LP goes": gross Jita value per LP, minus store ISK, required
 * items, freight in, sales tax and freight out. Costs switched off in the
 * filters are left out and added back into net.
 */
export function offer_lp_waterfall(
    offer: LoyaltyOffer,
    side: LoyaltyOffersSide,
    options: LoyaltyConversionCostOptions,
): LoyaltyLpWaterfall {
    const breakdown = loyalty_conversion_breakdown({
        lp_cost: offer.lp_cost,
        quantity: offer.quantity,
        market_price: market_price_for_side(offer, side),
        input_cost_isk: offer.input_cost_isk,
        costs: offer.conversion_costs?.[side],
        isk_cost: offer.isk_cost,
        other_cost: offer.other_cost,
        net_isk_per_lp: conversion_for_side(offer, side, true, true),
    })
    const lp = offer.lp_cost > 0 ? offer.lp_cost : null
    const store_isk = lp != null ? (offer.isk_cost || 0) / lp : 0
    const required_items = Math.max(0, (breakdown.input_isk_per_lp ?? 0) - store_isk)

    const candidates: Array<[LoyaltyLpWaterfallKey, number | null, boolean]> = [
        ['store_isk', store_isk, true],
        ['required_items', required_items, true],
        ['freight_in', breakdown.input_freight_isk_per_lp, options.include_freight],
        ['sales_tax', breakdown.sales_tax_isk_per_lp, options.include_sales_tax],
        ['freight_out', breakdown.output_freight_isk_per_lp, options.include_freight],
    ]
    const costs: LoyaltyLpWaterfall['costs'] = []
    for (const [key, value, included] of candidates) {
        if (!included || value == null || value <= 0)
            continue
        costs.push({ key, isk_per_lp: value })
    }

    return {
        gross_isk_per_lp: breakdown.raw_isk_per_lp,
        costs,
        net_isk_per_lp: conversion_for_side(
            offer,
            side,
            options.include_freight,
            options.include_sales_tax,
        ),
    }
}
