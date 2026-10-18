/**
 * LP offer ISK/LP hover breakdown.
 *
 * The backend owns the conversion (industry.helpers.plan_costing): the net and
 * the tax and freight inside it come from the API (`conversion_costs`). This
 * module only lines them up for the tooltip and the cost toggles.
 */

import type { LoyaltyOfferConversionCosts } from '@dtypes/api.minmatar.org'

export interface LoyaltyConversionBreakdown {
    raw_isk_per_lp: number | null
    input_isk_per_lp: number | null
    sales_tax_isk_per_lp: number | null
    input_freight_isk_per_lp: number | null
    output_freight_isk_per_lp: number | null
    net_isk_per_lp: number | null
}

export interface LoyaltyConversionBreakdownInput {
    lp_cost: number
    quantity: number
    market_price: number | null | undefined
    input_cost_isk: number | null | undefined
    /** This side's tax and freight per LP, as served by the API. */
    costs: LoyaltyOfferConversionCosts | null | undefined
    /** Fallback when API has not stored input_cost_isk yet. */
    isk_cost?: number | null
    /** Fallback for input cost. */
    other_cost?: number | null
    net_isk_per_lp: number | null | undefined
}

export interface LoyaltyConversionTipLabels {
    finished_goods: string
    other_cost: string
    input_freight: string
    sales_tax: string
    output_freight: string
    net: string
}

/** Which net-cost components are included in displayed ISK/LP. */
export interface LoyaltyConversionCostOptions {
    include_freight: boolean
    include_sales_tax: boolean
}

export const DEFAULT_CONVERSION_COST_OPTIONS: LoyaltyConversionCostOptions = {
    include_freight: true,
    include_sales_tax: true,
}

function per_lp(amount: number | null | undefined, lp_cost: number): number | null {
    if (amount == null || lp_cost <= 0)
        return null
    return amount / lp_cost
}

/**
 * Store ISK + required/mfg. Prefer API field; else isk_cost + other_cost.
 */
export function resolve_input_cost_isk(
    input: Pick<
        LoyaltyConversionBreakdownInput,
        'input_cost_isk' | 'isk_cost' | 'other_cost'
    >,
): number {
    if (input.input_cost_isk != null)
        return input.input_cost_isk
    return (input.isk_cost ?? 0) + (input.other_cost ?? 0)
}

export function loyalty_conversion_breakdown(
    input: LoyaltyConversionBreakdownInput,
): LoyaltyConversionBreakdown {
    const lp = input.lp_cost
    const qty = Math.max(input.quantity, 1)
    const revenue = input.market_price != null
        ? input.market_price * qty
        : null

    const input_cost = resolve_input_cost_isk(input)
    const costs = input.costs

    return {
        raw_isk_per_lp: per_lp(revenue, lp),
        input_isk_per_lp: per_lp(input_cost, lp),
        sales_tax_isk_per_lp: revenue != null ? costs?.sales_tax_isk_per_lp ?? null : null,
        input_freight_isk_per_lp: costs?.input_freight_isk_per_lp ?? null,
        output_freight_isk_per_lp: revenue != null ? costs?.output_freight_isk_per_lp ?? null : null,
        net_isk_per_lp: input.net_isk_per_lp ?? null,
    }
}

export function format_isk_per_lp_rate(value: number | null | undefined): string {
    if (value == null)
        return '—'
    return value.toLocaleString('en-US', {
        minimumFractionDigits: 1,
        maximumFractionDigits: 1,
    })
}

type TipSign = 'plus' | 'minus' | 'eq'

function tip_amount_line(
    sign: TipSign,
    value: number,
    label: string,
): string {
    if (sign === 'eq') {
        const amount = format_isk_per_lp_rate(value)
        return `= ${amount} ISK/LP (${label})`
    }
    const amount = format_isk_per_lp_rate(Math.abs(value))
    const prefix = sign === 'plus' ? '+' : '−'
    return `${prefix} ${amount} ISK/LP (${label})`
}

/** Sum of input + output freight ISK/LP components (0 when missing). */
export function freight_isk_per_lp_total(
    breakdown: Pick<
        LoyaltyConversionBreakdown,
        'input_freight_isk_per_lp' | 'output_freight_isk_per_lp'
    >,
): number {
    return (breakdown.input_freight_isk_per_lp ?? 0)
        + (breakdown.output_freight_isk_per_lp ?? 0)
}

/**
 * API net includes freight + sales tax. Add back any components that are
 * toggled off in the UI.
 */
export function net_isk_per_lp_for_cost_options(
    net_with_all_costs: number | null | undefined,
    breakdown: Pick<
        LoyaltyConversionBreakdown,
        | 'input_freight_isk_per_lp'
        | 'output_freight_isk_per_lp'
        | 'sales_tax_isk_per_lp'
    >,
    options: LoyaltyConversionCostOptions,
): number | null {
    if (net_with_all_costs == null)
        return null
    let net = net_with_all_costs
    if (!options.include_freight)
        net += freight_isk_per_lp_total(breakdown)
    if (!options.include_sales_tax)
        net += breakdown.sales_tax_isk_per_lp ?? 0
    return net
}

/**
 * Ledger-style tippy lines. Skips null/zero cost rows; keeps finished goods + net.
 * Omitted cost options skip their debit lines and are added back into net.
 */
export function loyalty_conversion_tip_lines(
    breakdown: LoyaltyConversionBreakdown,
    labels: LoyaltyConversionTipLabels,
    options: LoyaltyConversionCostOptions = DEFAULT_CONVERSION_COST_OPTIONS,
): string[] {
    const lines: string[] = []

    if (breakdown.raw_isk_per_lp != null) {
        lines.push(tip_amount_line(
            'plus',
            breakdown.raw_isk_per_lp,
            labels.finished_goods,
        ))
    }

    const debits: Array<[number | null, string]> = [
        [breakdown.input_isk_per_lp, labels.other_cost],
        ...(options.include_freight
            ? [[breakdown.input_freight_isk_per_lp, labels.input_freight] as const]
            : []),
        ...(options.include_sales_tax
            ? [[breakdown.sales_tax_isk_per_lp, labels.sales_tax] as const]
            : []),
        ...(options.include_freight
            ? [[breakdown.output_freight_isk_per_lp, labels.output_freight] as const]
            : []),
    ]
    for (const [value, label] of debits) {
        if (value == null || value === 0)
            continue
        lines.push(tip_amount_line('minus', value, label))
    }

    const net = net_isk_per_lp_for_cost_options(
        breakdown.net_isk_per_lp,
        breakdown,
        options,
    )
    if (net != null) {
        lines.push(tip_amount_line(
            'eq',
            net,
            labels.net,
        ))
    }

    return lines
}
