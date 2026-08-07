import { describe, expect, it } from 'vitest'

import { ops_sell_gaps_row_visible } from '@helpers/ops_sell_gaps_filter'

const understocked_overpriced = {
    item_type: 'high_slot',
    item_variant: 't2',
    flags: ['understocked', 'overpriced'],
}

const overstocked_overpriced = {
    item_type: 'consumable',
    item_variant: 't2',
    flags: ['overstocked', 'overpriced'],
}

const understocked_only = {
    item_type: 'hull',
    item_variant: 't1',
    flags: ['understocked'],
}

describe('ops_sell_gaps_row_visible', () => {
    it('shows all rows when no filters are selected', () => {
        expect(ops_sell_gaps_row_visible(overstocked_overpriced, [], [], [])).toBe(true)
        expect(ops_sell_gaps_row_visible(understocked_only, [], [], [])).toBe(true)
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
    })

    it('filters Overpriced to overpriced-tagged rows', () => {
        expect(
            ops_sell_gaps_row_visible(overstocked_overpriced, ['overpriced'], [], []),
        ).toBe(true)
        expect(
            ops_sell_gaps_row_visible(understocked_only, ['overpriced'], [], []),
        ).toBe(false)
    })

    it('ANDs multiple Criteria chips', () => {
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
                overstocked_overpriced,
                ['understocked', 'overpriced'],
                [],
                [],
            ),
        ).toBe(false)
        expect(
            ops_sell_gaps_row_visible(
                understocked_only,
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
