import { describe, expect, it } from 'vitest'

import {
    LP_CONVERSION_FREIGHT_RATE,
    LP_CONVERSION_SALES_TAX_RATE,
    loyalty_conversion_breakdown,
    loyalty_conversion_tip_lines,
    net_isk_per_lp_for_cost_options,
} from '@helpers/loyalty_conversion_breakdown'

const tip_labels = {
    finished_goods: 'finished goods',
    other_cost: 'other cost',
    input_freight: 'input freight',
    sales_tax: 'sales tax',
    output_freight: 'output freight',
    net: 'net',
}

describe('loyalty_conversion_breakdown', () => {
    it('matches Red Frog 45M / 1.5B and Accounting V tax', () => {
        expect(LP_CONVERSION_FREIGHT_RATE).toBeCloseTo(0.03, 10)
        expect(LP_CONVERSION_SALES_TAX_RATE).toBeCloseTo(0.0337, 10)
    })

    it('builds tippy components from market + stored input fields', () => {
        const result = loyalty_conversion_breakdown({
            lp_cost: 100_000,
            quantity: 1,
            market_price: 200_000_000,
            input_cost_isk: 50_000_000,
            input_freight_isk: 1_500_000,
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
            input_freight_isk: 15_000,
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
            input_freight_isk: null,
            isk_cost: 10_000_000,
            other_cost: 40_000_000,
            net_isk_per_lp: 1200,
        })
        expect(result.input_isk_per_lp).toBeCloseTo(500, 5)
        expect(result.input_freight_isk_per_lp).toBeCloseTo(
            Math.ceil(0.03 * 40_000_000) / 100_000,
            5,
        )
    })

    it('shows zero input lines when there are no extras', () => {
        const result = loyalty_conversion_breakdown({
            lp_cost: 100_000,
            quantity: 1,
            market_price: 200_000_000,
            input_cost_isk: null,
            input_freight_isk: null,
            isk_cost: 0,
            other_cost: 0,
            net_isk_per_lp: 1900,
        })
        expect(result.input_isk_per_lp).toBe(0)
        expect(result.input_freight_isk_per_lp).toBe(0)
    })

    it('formats a signed ledger and skips zero costs', () => {
        const breakdown = loyalty_conversion_breakdown({
            lp_cost: 100_000,
            quantity: 1,
            market_price: 200_000_000,
            input_cost_isk: 50_000_000,
            input_freight_isk: 0,
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
            input_freight_isk: 1_500_000,
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
            input_freight_isk: 1_500_000,
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
