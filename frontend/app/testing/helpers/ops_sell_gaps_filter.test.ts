import { describe, expect, it } from 'vitest'

import {
    ops_sell_gaps_compare_rows,
    ops_sell_gaps_default_direction,
    ops_sell_gaps_next_order_state,
    ops_sell_gaps_row_visible,
} from '@helpers/ops_sell_gaps_filter'

const understocked_overpriced = {
    item_name: 'Heavy Neutron Blaster II',
    item_type: 'high_slot',
    item_variant: 't2',
    flags: ['understocked', 'overpriced'],
    current_quantity: 10,
    shortfall: 40,
    weekly_units: 20,
    days_of_stock: 2,
    avg_markup_pct: 40,
}

const overstocked_overpriced = {
    item_name: 'Nanite Repair Paste',
    item_type: 'consumable',
    item_variant: 't2',
    flags: ['in_stock', 'overstocked', 'overpriced'],
    current_quantity: 200,
    shortfall: 0,
    weekly_units: 5,
    days_of_stock: 30,
    avg_markup_pct: 80,
}

const understocked_only = {
    item_name: 'Rifter',
    item_type: 'hull',
    item_variant: 't1',
    flags: ['understocked'],
    current_quantity: 5,
    shortfall: 10,
    weekly_units: 50,
    days_of_stock: 7,
    avg_markup_pct: 0,
}

const out_of_stock = {
    item_name: 'Scourge Torpedo',
    item_type: 'consumable',
    item_variant: 't1',
    flags: ['out_of_stock'],
    current_quantity: 0,
    shortfall: 100,
    weekly_units: 80,
    days_of_stock: null,
    avg_markup_pct: null,
}

const in_stock_only = {
    item_name: 'Hobgoblin I',
    item_type: 'drone',
    item_variant: 't1',
    flags: ['in_stock'],
    current_quantity: 50,
    shortfall: 0,
    weekly_units: 2,
    days_of_stock: 14,
    avg_markup_pct: 3,
}

describe('ops_sell_gaps_row_visible', () => {
    it('shows all rows when no filters are selected', () => {
        expect(ops_sell_gaps_row_visible(overstocked_overpriced, [], [], [])).toBe(true)
        expect(ops_sell_gaps_row_visible(understocked_only, [], [], [])).toBe(true)
        expect(ops_sell_gaps_row_visible(in_stock_only, [], [], [])).toBe(true)
    })

    it('filters Out of Stock to empty-stock rows', () => {
        expect(
            ops_sell_gaps_row_visible(out_of_stock, ['out_of_stock'], [], []),
        ).toBe(true)
        expect(
            ops_sell_gaps_row_visible(understocked_only, ['out_of_stock'], [], []),
        ).toBe(false)
        expect(
            ops_sell_gaps_row_visible(in_stock_only, ['out_of_stock'], [], []),
        ).toBe(false)
    })

    it('filters Understocked to understocked-tagged rows', () => {
        expect(
            ops_sell_gaps_row_visible(understocked_overpriced, ['understocked'], [], []),
        ).toBe(true)
        expect(
            ops_sell_gaps_row_visible(understocked_only, ['understocked'], [], []),
        ).toBe(true)
        expect(
            ops_sell_gaps_row_visible(overstocked_overpriced, ['understocked'], [], []),
        ).toBe(false)
        expect(
            ops_sell_gaps_row_visible(out_of_stock, ['understocked'], [], []),
        ).toBe(false)
    })

    it('ORs stock-status Criteria chips (default Out of Stock + Understocked)', () => {
        expect(
            ops_sell_gaps_row_visible(
                out_of_stock,
                ['out_of_stock', 'understocked'],
                [],
                [],
            ),
        ).toBe(true)
        expect(
            ops_sell_gaps_row_visible(
                understocked_only,
                ['out_of_stock', 'understocked'],
                [],
                [],
            ),
        ).toBe(true)
        expect(
            ops_sell_gaps_row_visible(
                in_stock_only,
                ['out_of_stock', 'understocked'],
                [],
                [],
            ),
        ).toBe(false)
    })

    it('filters In Stock to in-stock-tagged rows', () => {
        expect(
            ops_sell_gaps_row_visible(in_stock_only, ['in_stock'], [], []),
        ).toBe(true)
        expect(
            ops_sell_gaps_row_visible(overstocked_overpriced, ['in_stock'], [], []),
        ).toBe(true)
        expect(
            ops_sell_gaps_row_visible(understocked_only, ['in_stock'], [], []),
        ).toBe(false)
    })

    it('filters Overpriced to overpriced-tagged rows', () => {
        expect(
            ops_sell_gaps_row_visible(overstocked_overpriced, ['overpriced'], [], []),
        ).toBe(true)
        expect(
            ops_sell_gaps_row_visible(understocked_only, ['overpriced'], [], []),
        ).toBe(false)
    })

    it('ANDs Overpriced with stock-status Criteria', () => {
        expect(
            ops_sell_gaps_row_visible(
                understocked_overpriced,
                ['understocked', 'overpriced'],
                [],
                [],
            ),
        ).toBe(true)
        expect(
            ops_sell_gaps_row_visible(
                understocked_only,
                ['understocked', 'overpriced'],
                [],
                [],
            ),
        ).toBe(false)
        expect(
            ops_sell_gaps_row_visible(
                overstocked_overpriced,
                ['in_stock', 'overpriced'],
                [],
                [],
            ),
        ).toBe(true)
        expect(
            ops_sell_gaps_row_visible(
                overstocked_overpriced,
                ['understocked', 'overpriced'],
                [],
                [],
            ),
        ).toBe(false)
    })

    it('ORs Type chips within the group', () => {
        expect(
            ops_sell_gaps_row_visible(
                understocked_only,
                [],
                ['hull', 'drone'],
                [],
            ),
        ).toBe(true)
        expect(
            ops_sell_gaps_row_visible(
                overstocked_overpriced,
                [],
                ['hull', 'drone'],
                [],
            ),
        ).toBe(false)
    })

    it('filters by item name search (case-insensitive substring)', () => {
        expect(
            ops_sell_gaps_row_visible(understocked_only, [], [], [], 'rif'),
        ).toBe(true)
        expect(
            ops_sell_gaps_row_visible(understocked_only, [], [], [], 'RIFTER'),
        ).toBe(true)
        expect(
            ops_sell_gaps_row_visible(understocked_only, [], [], [], 'nanite'),
        ).toBe(false)
        expect(
            ops_sell_gaps_row_visible(overstocked_overpriced, [], [], [], '  paste  '),
        ).toBe(true)
    })

    it('treats missing flags as empty', () => {
        expect(
            ops_sell_gaps_row_visible(
                { item_type: 'other', item_variant: 'other' },
                ['understocked'],
                [],
                [],
            ),
        ).toBe(false)
    })
})

describe('ops_sell_gaps_compare_rows', () => {
    it('defaults to days of stock ascending (least remaining first)', () => {
        const sorted = [
            out_of_stock,
            understocked_overpriced,
            understocked_only,
            overstocked_overpriced,
        ].sort((a, b) => ops_sell_gaps_compare_rows(a, b))

        expect(sorted.map(row => row.item_name)).toEqual([
            'Scourge Torpedo',
            'Heavy Neutron Blaster II',
            'Rifter',
            'Nanite Repair Paste',
        ])
    })

    it('orders by days of stock ascending when selected', () => {
        const sorted = [
            out_of_stock,
            understocked_overpriced,
            understocked_only,
            overstocked_overpriced,
        ].sort((a, b) => ops_sell_gaps_compare_rows(a, b, 'days_of_stock'))

        expect(sorted.map(row => row.item_name)).toEqual([
            'Scourge Torpedo',
            'Heavy Neutron Blaster II',
            'Rifter',
            'Nanite Repair Paste',
        ])
    })

    it('orders by markup descending (highest first)', () => {
        const sorted = [
            understocked_only,
            understocked_overpriced,
            overstocked_overpriced,
            out_of_stock,
        ].sort((a, b) => ops_sell_gaps_compare_rows(a, b, 'markup'))

        expect(sorted.map(row => row.item_name)).toEqual([
            'Nanite Repair Paste',
            'Heavy Neutron Blaster II',
            'Rifter',
            'Scourge Torpedo',
        ])
    })

    it('orders by 7d volume descending', () => {
        const sorted = [
            understocked_only,
            understocked_overpriced,
            overstocked_overpriced,
            out_of_stock,
        ].sort((a, b) => ops_sell_gaps_compare_rows(a, b, 'volume_7d'))

        expect(sorted.map(row => row.item_name)).toEqual([
            'Scourge Torpedo',
            'Rifter',
            'Heavy Neutron Blaster II',
            'Nanite Repair Paste',
        ])
    })

    it('falls back to days of stock for unknown order-by ids', () => {
        const sorted = [
            out_of_stock,
            understocked_overpriced,
            understocked_only,
            overstocked_overpriced,
        ].sort((a, b) => ops_sell_gaps_compare_rows(a, b, 'not_a_real_sort'))

        expect(sorted.map(row => row.item_name)).toEqual([
            'Scourge Torpedo',
            'Heavy Neutron Blaster II',
            'Rifter',
            'Nanite Repair Paste',
        ])
    })

    it('orders by days of stock descending when direction flipped', () => {
        const sorted = [
            out_of_stock,
            understocked_overpriced,
            understocked_only,
            overstocked_overpriced,
        ].sort((a, b) => ops_sell_gaps_compare_rows(a, b, 'days_of_stock', 'desc'))

        expect(sorted.map(row => row.item_name)).toEqual([
            'Nanite Repair Paste',
            'Rifter',
            'Heavy Neutron Blaster II',
            'Scourge Torpedo',
        ])
    })

    it('orders by markup ascending when direction flipped', () => {
        const sorted = [
            understocked_only,
            understocked_overpriced,
            overstocked_overpriced,
            out_of_stock,
        ].sort((a, b) => ops_sell_gaps_compare_rows(a, b, 'markup', 'asc'))

        expect(sorted.map(row => row.item_name)).toEqual([
            'Rifter',
            'Heavy Neutron Blaster II',
            'Nanite Repair Paste',
            'Scourge Torpedo',
        ])
    })
})

describe('ops_sell_gaps_next_order_state', () => {
    it('selects a new key with its default direction', () => {
        expect(
            ops_sell_gaps_next_order_state('days_of_stock', 'asc', 'markup'),
        ).toEqual({ order_by: 'markup', direction: 'desc' })
        expect(ops_sell_gaps_default_direction('volume_7d')).toBe('desc')
    })

    it('flips direction when the active pill is clicked again', () => {
        expect(
            ops_sell_gaps_next_order_state('days_of_stock', 'asc', 'days_of_stock'),
        ).toEqual({ order_by: 'days_of_stock', direction: 'desc' })
        expect(
            ops_sell_gaps_next_order_state('markup', 'desc', 'markup'),
        ).toEqual({ order_by: 'markup', direction: 'asc' })
    })
})
