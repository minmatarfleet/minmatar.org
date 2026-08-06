/**
 * LP offer ISK/LP hover breakdown (mirrors backend plan_lp_offer_conversion).
 *
 * Net conversion already includes these; tippy shows the components.
 */

export const LP_CONVERSION_SALES_TAX_RATE = 0.0337
/** Red Frog: 45M ISK per 1.5B cargo. */
export const LP_CONVERSION_FREIGHT_RATE = 45_000_000 / 1_500_000_000

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
    input_freight_isk: number | null | undefined
    /** Fallback when API has not stored input_cost_isk yet. */
    isk_cost?: number | null
    /** Fallback for input cost + input-freight basis. */
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

/**
 * Red Frog on required items / materials. Prefer API field; else % of other_cost.
 */
export function resolve_input_freight_isk(
    input: Pick<
        LoyaltyConversionBreakdownInput,
        'input_freight_isk' | 'other_cost'
    >,
): number {
    if (input.input_freight_isk != null)
        return input.input_freight_isk
    const basis = input.other_cost ?? 0
    if (basis <= 0)
        return 0
    return Math.ceil(LP_CONVERSION_FREIGHT_RATE * basis)
}

export function loyalty_conversion_breakdown(
    input: LoyaltyConversionBreakdownInput,
): LoyaltyConversionBreakdown {
    const lp = input.lp_cost
    const qty = Math.max(input.quantity, 1)
    const revenue = input.market_price != null
        ? input.market_price * qty
        : null

    const sales_tax = revenue != null
        ? Math.ceil(LP_CONVERSION_SALES_TAX_RATE * revenue)
        : null
    const output_freight = revenue != null
        ? Math.ceil(LP_CONVERSION_FREIGHT_RATE * revenue)
        : null
    const input_cost = resolve_input_cost_isk(input)
    const input_freight = resolve_input_freight_isk(input)

    return {
        raw_isk_per_lp: per_lp(revenue, lp),
        input_isk_per_lp: per_lp(input_cost, lp),
        sales_tax_isk_per_lp: per_lp(sales_tax, lp),
        input_freight_isk_per_lp: per_lp(input_freight, lp),
        output_freight_isk_per_lp: per_lp(output_freight, lp),
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

/**
 * Ledger-style tippy lines. Skips null/zero cost rows; keeps finished goods + net.
 */
export function loyalty_conversion_tip_lines(
    breakdown: LoyaltyConversionBreakdown,
    labels: LoyaltyConversionTipLabels,
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
        [breakdown.input_freight_isk_per_lp, labels.input_freight],
        [breakdown.sales_tax_isk_per_lp, labels.sales_tax],
        [breakdown.output_freight_isk_per_lp, labels.output_freight],
    ]
    for (const [value, label] of debits) {
        if (value == null || value === 0)
            continue
        lines.push(tip_amount_line('minus', value, label))
    }

    if (breakdown.net_isk_per_lp != null) {
        lines.push(tip_amount_line(
            'eq',
            breakdown.net_isk_per_lp,
            labels.net,
        ))
    }

    return lines
}
