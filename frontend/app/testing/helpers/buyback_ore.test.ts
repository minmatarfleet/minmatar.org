import { describe, expect, it } from 'vitest'

import {
    buyback_ore_base,
    compressed_buyback_ore_base,
    group_stock_items,
    janice_tsv_from_stock_groups,
    type StockGroupItem,
} from '@helpers/buyback_ore'

function item(overrides: Partial<StockGroupItem> & Pick<StockGroupItem, 'name'>): StockGroupItem {
    return {
        type_id: overrides.type_id ?? 1,
        category: overrides.category ?? null,
        quantity: overrides.quantity ?? 1,
        demand_status: overrides.demand_status ?? 'in_demand',
        isk_value: overrides.isk_value ?? 0,
        ...overrides,
    }
}

describe('janice_tsv_from_stock_groups', () => {
    it('copies variant names for grouped ore, not the group label', () => {
        const tsv = janice_tsv_from_stock_groups([
            {
                label: 'Veldspar',
                quantity: 1500,
                variants: [
                    { name: 'Compressed Veldspar', quantity: 1000 },
                    { name: 'Compressed Veldspar II-Grade', quantity: 500 },
                ],
            },
        ])
        expect(tsv).toBe(
            'Compressed Veldspar\t1000\r\nCompressed Veldspar II-Grade\t500',
        )
        expect(tsv).not.toContain('Veldspar\t1500')
    })

    it('copies the real name when a group has one variant', () => {
        const tsv = janice_tsv_from_stock_groups([
            {
                label: 'Veldspar',
                quantity: 100,
                variants: [{ name: 'Compressed Veldspar', quantity: 100 }],
            },
        ])
        expect(tsv).toBe('Compressed Veldspar\t100')
    })

    it('copies leftover PI by item name', () => {
        const tsv = janice_tsv_from_stock_groups([
            {
                label: 'Water',
                quantity: 50,
                variants: [],
            },
        ])
        expect(tsv).toBe('Water\t50')
    })
})

describe('buyback_ore_base', () => {
    it('matches compressed grades and uncompressed family names', () => {
        expect(buyback_ore_base('Compressed Veldspar II-Grade')).toBe('Veldspar')
        expect(buyback_ore_base('Ytirium')).toBe('Ytirium')
        expect(compressed_buyback_ore_base('Ytirium')).toBeNull()
    })
})

describe('group_stock_items', () => {
    it('lists ore families before PI, each in low-to-high tier order', () => {
        const groups = group_stock_items([
            item({
                type_id: 3,
                name: 'Robotics',
                category: 'p3',
                isk_value: 9_000_000_000,
            }),
            item({
                type_id: 1,
                name: 'Compressed Crokite',
                category: 'ore',
                isk_value: 50_000_000,
            }),
            item({
                type_id: 4,
                name: 'Water',
                category: 'p1',
                isk_value: 200_000_000,
            }),
            item({
                type_id: 2,
                name: 'Compressed Veldspar',
                category: 'ore',
                isk_value: 4_000_000_000,
            }),
            item({
                type_id: 5,
                name: 'Coolant',
                category: 'p2',
                isk_value: 1_900_000_000,
            }),
        ])

        expect(groups.map((group) => group.label)).toEqual([
            'Veldspar',
            'Crokite',
            'Water',
            'Coolant',
            'Robotics',
        ])
        expect(groups.map((group) => group.category)).toEqual([
            'ore',
            'ore',
            'p1',
            'p2',
            'p3',
        ])
    })

    it('groups uncompressed ore with its compressed family', () => {
        const groups = group_stock_items([
            item({ type_id: 10, name: 'Ytirium', category: 'ore', quantity: 100 }),
            item({
                type_id: 11,
                name: 'Compressed Ytirium',
                category: 'ore',
                quantity: 50,
            }),
        ])

        expect(groups).toHaveLength(1)
        expect(groups[0]?.label).toBe('Ytirium')
        expect(groups[0]?.quantity).toBe(150)
        expect(groups[0]?.variants.map((variant) => variant.name)).toEqual([
            'Compressed Ytirium',
            'Ytirium',
        ])
    })
})
