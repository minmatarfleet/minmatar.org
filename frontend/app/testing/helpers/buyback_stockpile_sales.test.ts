import { describe, expect, it } from 'vitest'
import type { BuybackLedgerEntry } from '@dtypes/api.minmatar.org'
import { aggregate_stockpile_sales } from '@helpers/buyback_stockpile_sales'

function entry(partial: Partial<BuybackLedgerEntry> & Pick<BuybackLedgerEntry, 'id' | 'type_id' | 'name' | 'quantity' | 'occurred_at' | 'reason'>): BuybackLedgerEntry {
    return {
        unit_price: null,
        isk_total: null,
        source_id: `src-${partial.id}`,
        location_id: null,
        ...partial,
    }
}

describe('aggregate_stockpile_sales', () => {
    it('rolls up same item on the same day', () => {
        const rows = aggregate_stockpile_sales([
            entry({
                id: 1,
                type_id: 10,
                name: 'Biocells',
                quantity: 1000,
                isk_total: 10_000_000,
                reason: 'sold_order',
                occurred_at: '2026-08-18T23:53:32Z',
                counterparty_id: 1,
                counterparty_name: 'ThisShit',
                counterparty_kind: 'character',
            }),
            entry({
                id: 2,
                type_id: 10,
                name: 'Biocells',
                quantity: 30_000,
                isk_total: 300_000_000,
                reason: 'sold_order',
                occurred_at: '2026-08-18T23:53:17Z',
                counterparty_id: 1,
                counterparty_name: 'ThisShit',
                counterparty_kind: 'character',
            }),
            entry({
                id: 3,
                type_id: 10,
                name: 'Biocells',
                quantity: 1870,
                isk_total: 18_000_000,
                reason: 'sold_order',
                occurred_at: '2026-08-18T23:32:33Z',
                counterparty_id: 2,
                counterparty_name: 'HennyNredbull',
                counterparty_kind: 'character',
            }),
        ])

        expect(rows).toHaveLength(1)
        expect(rows[0].quantity).toBe(32_870)
        expect(rows[0].isk_total).toBe(328_000_000)
        expect(rows[0].sale_count).toBe(3)
        expect(rows[0].buyers.map((b) => b.counterparty_name)).toEqual([
            'ThisShit',
            'HennyNredbull',
        ])
    })

    it('keeps different days and reasons separate', () => {
        const rows = aggregate_stockpile_sales([
            entry({
                id: 1,
                type_id: 10,
                name: 'Biocells',
                quantity: 100,
                isk_total: 1,
                reason: 'sold_order',
                occurred_at: '2026-08-18T12:00:00Z',
            }),
            entry({
                id: 2,
                type_id: 10,
                name: 'Biocells',
                quantity: 50,
                isk_total: 1,
                reason: 'sold_order',
                occurred_at: '2026-08-17T12:00:00Z',
            }),
            entry({
                id: 3,
                type_id: 10,
                name: 'Biocells',
                quantity: 25,
                isk_total: 1,
                reason: 'sold_contract',
                occurred_at: '2026-08-18T12:00:00Z',
            }),
        ])

        expect(rows).toHaveLength(3)
    })
})
