import { describe, expect, it } from 'vitest'

import {
    loyalty_conversion_breakdown,
    loyalty_conversion_tip_lines,
    net_isk_per_lp_for_cost_options,
    type LoyaltyConversionBreakdown,
} from '@helpers/loyalty_conversion_breakdown'
import { api_side_costs } from './fixtures/loyalty_api_costs'
import backend_fixture from './fixtures/loyalty_offer_costs_backend.json'

const tip_labels = {
    finished_goods: 'finished goods',
    other_cost: 'other cost',
    input_freight: 'input freight',
    sales_tax: 'sales tax',
    output_freight: 'output freight',
    net: 'net',
}

describe('loyalty_conversion_breakdown', () => {
    it('builds tippy components from market + stored input fields', () => {
        const result = loyalty_conversion_breakdown({
            lp_cost: 100_000,
            quantity: 1,
            market_price: 200_000_000,
            input_cost_isk: 50_000_000,
            costs: api_side_costs(100_000, 1, 200_000_000, 1_500_000),
            net_isk_per_lp: 1200,
        })
        expect(result.raw_isk_per_lp).toBeCloseTo(2000, 5)
        expect(result.input_isk_per_lp).toBeCloseTo(500, 5)
        expect(result.sales_tax_isk_per_lp).toBeCloseTo(
            Math.ceil(0.0337 * 200_000_000) / 100_000,
            5,
        )
        expect(result.input_freight_isk_per_lp).toBeCloseTo(15, 5)
        expect(result.output_freight_isk_per_lp).toBeCloseTo(
            Math.ceil(0.03 * 200_000_000) / 100_000,
            5,
        )
        expect(result.net_isk_per_lp).toBe(1200)
    })

    it('returns nulls when market price is missing', () => {
        const result = loyalty_conversion_breakdown({
            lp_cost: 1000,
            quantity: 1,
            market_price: null,
            input_cost_isk: 500_000,
            costs: api_side_costs(1000, 1, null, 15_000),
            net_isk_per_lp: null,
        })
        expect(result.raw_isk_per_lp).toBeNull()
        expect(result.sales_tax_isk_per_lp).toBeNull()
        expect(result.output_freight_isk_per_lp).toBeNull()
        expect(result.input_isk_per_lp).toBeCloseTo(500, 5)
    })

    it('falls back to isk_cost + other_cost when input fields are missing', () => {
        const result = loyalty_conversion_breakdown({
            lp_cost: 100_000,
            quantity: 1,
            market_price: 200_000_000,
            input_cost_isk: null,
            costs: api_side_costs(100_000, 1, 200_000_000, null),
            isk_cost: 10_000_000,
            other_cost: 40_000_000,
            net_isk_per_lp: 1200,
        })
        expect(result.input_isk_per_lp).toBeCloseTo(500, 5)
        // Freight comes only from the API; no stored input freight, no line.
        expect(result.input_freight_isk_per_lp).toBeNull()
    })

    it('shows zero input lines when there are no extras', () => {
        const result = loyalty_conversion_breakdown({
            lp_cost: 100_000,
            quantity: 1,
            market_price: 200_000_000,
            input_cost_isk: null,
            costs: api_side_costs(100_000, 1, 200_000_000, null),
            isk_cost: 0,
            other_cost: 0,
            net_isk_per_lp: 1900,
        })
        expect(result.input_isk_per_lp).toBe(0)
        expect(result.input_freight_isk_per_lp).toBeNull()
    })

    it('formats a signed ledger and skips zero costs', () => {
        const breakdown = loyalty_conversion_breakdown({
            lp_cost: 100_000,
            quantity: 1,
            market_price: 200_000_000,
            input_cost_isk: 50_000_000,
            costs: api_side_costs(100_000, 1, 200_000_000, 0),
            net_isk_per_lp: 1200,
        })
        expect(loyalty_conversion_tip_lines(breakdown, tip_labels)).toEqual([
            '+ 2,000.0 ISK/LP (finished goods)',
            '− 500.0 ISK/LP (other cost)',
            '− 67.4 ISK/LP (sales tax)',
            '− 60.0 ISK/LP (output freight)',
            '= 1,200.0 ISK/LP (net)',
        ])
    })

    it('omits freight lines and adds freight back into net when excluded', () => {
        const breakdown = loyalty_conversion_breakdown({
            lp_cost: 100_000,
            quantity: 1,
            market_price: 200_000_000,
            input_cost_isk: 50_000_000,
            costs: api_side_costs(100_000, 1, 200_000_000, 1_500_000),
            net_isk_per_lp: 1200,
        })
        expect(loyalty_conversion_tip_lines(breakdown, tip_labels, {
            include_freight: false,
            include_sales_tax: true,
        })).toEqual([
            '+ 2,000.0 ISK/LP (finished goods)',
            '− 500.0 ISK/LP (other cost)',
            '− 67.4 ISK/LP (sales tax)',
            '= 1,275.0 ISK/LP (net)',
        ])
    })

    it('omits sales tax and adds it back into net when excluded', () => {
        const breakdown = loyalty_conversion_breakdown({
            lp_cost: 100_000,
            quantity: 1,
            market_price: 200_000_000,
            input_cost_isk: 50_000_000,
            costs: api_side_costs(100_000, 1, 200_000_000, 1_500_000),
            net_isk_per_lp: 1200,
        })
        expect(loyalty_conversion_tip_lines(breakdown, tip_labels, {
            include_freight: true,
            include_sales_tax: false,
        })).toEqual([
            '+ 2,000.0 ISK/LP (finished goods)',
            '− 500.0 ISK/LP (other cost)',
            '− 15.0 ISK/LP (input freight)',
            '− 60.0 ISK/LP (output freight)',
            '= 1,267.4 ISK/LP (net)',
        ])
    })
})

describe('net_isk_per_lp_for_cost_options', () => {
    it('returns net unchanged when all costs are included', () => {
        expect(net_isk_per_lp_for_cost_options(
            1200,
            {
                input_freight_isk_per_lp: 15,
                output_freight_isk_per_lp: 60,
                sales_tax_isk_per_lp: 67.4,
            },
            { include_freight: true, include_sales_tax: true },
        )).toBe(1200)
    })

    it('adds freight and sales tax back when excluded', () => {
        expect(net_isk_per_lp_for_cost_options(
            1200,
            {
                input_freight_isk_per_lp: 15,
                output_freight_isk_per_lp: 60,
                sales_tax_isk_per_lp: 67.4,
            },
            { include_freight: false, include_sales_tax: false },
        )).toBeCloseTo(1342.4, 5)
    })
})

// The frontend's former re-derivation (rates copied from the backend), kept to
// prove the API-served costs give the same tooltip and toggle numbers today.
function legacy_breakdown(input: {
    lp_cost: number, quantity: number, market_price: number | null,
    input_cost_isk: number | null, input_freight_isk: number | null,
    isk_cost?: number | null, other_cost?: number | null, net_isk_per_lp: number | null,
}): LoyaltyConversionBreakdown {
    const per_lp = (amount: number | null) => amount == null || input.lp_cost <= 0 ? null : amount / input.lp_cost
    const revenue = input.market_price != null ? input.market_price * Math.max(input.quantity, 1) : null
    const input_cost = input.input_cost_isk ?? (input.isk_cost ?? 0) + (input.other_cost ?? 0)
    const freight_basis = input.other_cost ?? 0
    const input_freight = input.input_freight_isk ?? (freight_basis <= 0 ? 0 : Math.ceil(0.03 * freight_basis))
    return {
        raw_isk_per_lp: per_lp(revenue),
        input_isk_per_lp: per_lp(input_cost),
        sales_tax_isk_per_lp: per_lp(revenue != null ? Math.ceil(0.0337 * revenue) : null),
        input_freight_isk_per_lp: per_lp(input_freight),
        output_freight_isk_per_lp: per_lp(revenue != null ? Math.ceil((45_000_000 / 1_500_000_000) * revenue) : null),
        net_isk_per_lp: input.net_isk_per_lp,
    }
}

describe('API-served conversion costs', () => {
    const sides = [['sell', 'jita_sell'], ['buy', 'jita_buy'], ['avg_7d', 'jita_avg_7d']] as const
    const option_sets = [
        { include_freight: true, include_sales_tax: true },
        { include_freight: false, include_sales_tax: true },
        { include_freight: true, include_sales_tax: false },
        { include_freight: false, include_sales_tax: false },
    ]

    it('the test helper matches what the backend serves', () => {
        for (const row of backend_fixture.offers) {
            for (const [side, price_key] of sides) {
                const price = row[price_key]
                const served = (row.conversion_costs as Record<string, unknown>)[side]
                if (price == null) {
                    expect(served).toBeUndefined()
                    continue
                }
                expect(served).toEqual(api_side_costs(row.lp_cost, row.quantity, price, row.input_freight_isk))
            }
        }
    })

    it('give the same tooltip lines and toggled nets as the old frontend math', () => {
        for (const row of backend_fixture.offers) {
            for (const [side, price_key] of sides) {
                const price = row[price_key]
                if (price == null) continue
                // other_cost is null exactly when the backend stored no input freight.
                const other_cost = row.input_freight_isk == null ? null : 40_000
                const shared = {
                    lp_cost: row.lp_cost,
                    quantity: row.quantity,
                    market_price: price,
                    input_cost_isk: row.input_freight_isk == null ? null : 123_456,
                    isk_cost: 10_000,
                    other_cost,
                    net_isk_per_lp: 1234.5,
                }
                const legacy = legacy_breakdown({ ...shared, input_freight_isk: row.input_freight_isk })
                const current = loyalty_conversion_breakdown({
                    ...shared,
                    costs: (row.conversion_costs as Record<string, any>)[side],
                })
                for (const options of option_sets) {
                    expect(loyalty_conversion_tip_lines(current, tip_labels, options))
                        .toEqual(loyalty_conversion_tip_lines(legacy, tip_labels, options))
                    expect(net_isk_per_lp_for_cost_options(1234.5, current, options))
                        .toBeCloseTo(net_isk_per_lp_for_cost_options(1234.5, legacy, options) as number, 9)
                }
            }
        }
    })
})
