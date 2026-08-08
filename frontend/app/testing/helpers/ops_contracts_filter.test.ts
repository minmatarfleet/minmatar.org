import { describe, expect, it } from 'vitest'

import {
    OPS_CONTRACTS_DEFAULT_CRITERIA,
    OPS_CONTRACTS_NO_DOCTRINE,
    ops_contracts_compare_rows,
    ops_contracts_default_direction,
    ops_contracts_next_order_state,
    ops_contracts_row_visible,
    ops_contracts_stock_status,
} from '@helpers/ops_contracts_filter'

        const unstocked = {
    title: 'Empty Fit',
    fitting_id: 1,
    stock_status: 'unstocked' as const,
    doctrine_ids: [1],
    fill_pct: 0,
    volume_28d: 2,
    fleets_remaining: 0,
}

const low_stock = {
    title: 'Thin Fit',
    fitting_id: 2,
    stock_status: 'low_stock' as const,
    doctrine_ids: [1, 2],
    fill_pct: 40,
    volume_28d: 10,
    fleets_remaining: 3,
}

const in_stock = {
    title: 'Ready Fit',
    fitting_id: 3,
    stock_status: 'in_stock' as const,
    doctrine_ids: [2],
    fill_pct: 100,
    volume_28d: 5,
    fleets_remaining: 8,
}

const overstocked = {
    title: 'Over Fit',
    fitting_id: 4,
    stock_status: 'overstocked' as const,
    doctrine_ids: [2],
    fill_pct: 100,
    volume_28d: 1,
    fleets_remaining: 12,
}

const no_target = {
    title: 'Unknown Fit',
    fitting_id: 5,
    stock_status: null,
    doctrine_ids: [],
    fill_pct: null,
    volume_28d: 0,
    fleets_remaining: null,
}

describe('ops_contracts_stock_status', () => {
    it('maps qty vs target into criteria buckets', () => {
        expect(ops_contracts_stock_status(0, 10)).toBe('unstocked')
        expect(ops_contracts_stock_status(4, 10)).toBe('low_stock')
        expect(ops_contracts_stock_status(10, 10)).toBe('in_stock')
        expect(ops_contracts_stock_status(12, 10)).toBe('overstocked')
        expect(ops_contracts_stock_status(5, 0)).toBeNull()
    })
})

describe('ops_contracts_row_visible', () => {
    it('shows all rows when no filters are selected', () => {
        expect(ops_contracts_row_visible(unstocked, [], [], '')).toBe(true)
        expect(ops_contracts_row_visible(in_stock, [], [], '')).toBe(true)
        expect(ops_contracts_row_visible(no_target, [], [], '')).toBe(true)
    })

    it('defaults to unstocked + low stock', () => {
        expect(OPS_CONTRACTS_DEFAULT_CRITERIA).toEqual(['unstocked', 'low_stock'])
        expect(
            ops_contracts_row_visible(unstocked, OPS_CONTRACTS_DEFAULT_CRITERIA, [], ''),
        ).toBe(true)
        expect(
            ops_contracts_row_visible(low_stock, OPS_CONTRACTS_DEFAULT_CRITERIA, [], ''),
        ).toBe(true)
        expect(
            ops_contracts_row_visible(in_stock, OPS_CONTRACTS_DEFAULT_CRITERIA, [], ''),
        ).toBe(false)
        expect(
            ops_contracts_row_visible(overstocked, OPS_CONTRACTS_DEFAULT_CRITERIA, [], ''),
        ).toBe(false)
        expect(
            ops_contracts_row_visible(no_target, OPS_CONTRACTS_DEFAULT_CRITERIA, [], ''),
        ).toBe(false)
    })

    it('filters stock criteria with OR', () => {
        expect(ops_contracts_row_visible(unstocked, ['unstocked'], [], '')).toBe(true)
        expect(ops_contracts_row_visible(low_stock, ['unstocked'], [], '')).toBe(false)
        expect(
            ops_contracts_row_visible(low_stock, ['unstocked', 'low_stock'], [], ''),
        ).toBe(true)
        expect(
            ops_contracts_row_visible(in_stock, ['in_stock', 'overstocked'], [], ''),
        ).toBe(true)
        expect(
            ops_contracts_row_visible(overstocked, ['in_stock', 'overstocked'], [], ''),
        ).toBe(true)
    })

    it('filters doctrines with OR including none', () => {
        expect(ops_contracts_row_visible(unstocked, [], ['1'], '')).toBe(true)
        expect(ops_contracts_row_visible(in_stock, [], ['1'], '')).toBe(false)
        expect(ops_contracts_row_visible(low_stock, [], ['2'], '')).toBe(true)
        expect(
            ops_contracts_row_visible(no_target, [], [OPS_CONTRACTS_NO_DOCTRINE], ''),
        ).toBe(true)
        expect(
            ops_contracts_row_visible(unstocked, [], [OPS_CONTRACTS_NO_DOCTRINE], ''),
        ).toBe(false)
    })

    it('filters by title search substring', () => {
        expect(ops_contracts_row_visible(low_stock, [], [], 'thin')).toBe(true)
        expect(ops_contracts_row_visible(low_stock, [], [], 'ready')).toBe(false)
        expect(ops_contracts_row_visible(in_stock, [], [], 'FIT')).toBe(true)
    })
})

describe('ops_contracts_compare_rows', () => {
    it('sorts stock fill desc by default with missing last', () => {
        const ranked = [unstocked, in_stock, no_target, low_stock]
            .slice()
            .sort((a, b) => ops_contracts_compare_rows(a, b))
        expect(ranked.map(r => r.title)).toEqual([
            'Ready Fit',
            'Thin Fit',
            'Empty Fit',
            'Unknown Fit',
        ])
    })

    it('sorts volume_28d desc', () => {
        const ranked = [unstocked, in_stock, low_stock]
            .slice()
            .sort((a, b) =>
                ops_contracts_compare_rows(a, b, 'volume_28d', 'desc'),
            )
        expect(ranked.map(r => r.title)).toEqual([
            'Thin Fit',
            'Ready Fit',
            'Empty Fit',
        ])
    })

    it('sorts fleets_remaining asc with missing last', () => {
        const ranked = [in_stock, unstocked, no_target, low_stock]
            .slice()
            .sort((a, b) =>
                ops_contracts_compare_rows(a, b, 'fleets_remaining', 'asc'),
            )
        expect(ranked.map(r => r.title)).toEqual([
            'Empty Fit',
            'Thin Fit',
            'Ready Fit',
            'Unknown Fit',
        ])
    })
})

describe('ops_contracts_next_order_state', () => {
    it('flips direction on same pill', () => {
        expect(
            ops_contracts_next_order_state('stock_fill', 'desc', 'stock_fill'),
        ).toEqual({ order_by: 'stock_fill', direction: 'asc' })
    })

    it('selects new pill with its default direction', () => {
        expect(
            ops_contracts_next_order_state('stock_fill', 'desc', 'volume_28d'),
        ).toEqual({ order_by: 'volume_28d', direction: 'desc' })
        expect(
            ops_contracts_next_order_state('stock_fill', 'desc', 'fleets_remaining'),
        ).toEqual({ order_by: 'fleets_remaining', direction: 'asc' })
        expect(ops_contracts_default_direction('fleets_remaining')).toBe('asc')
    })
})
