import { describe, expect, it } from 'vitest'
import {
    busiest_hours,
    heatmap_cells,
    mix_rows,
    month_label,
    percent_shares,
    prime_spans,
    ranked_mix_rows,
    tenure_parts,
} from '@helpers/corporations/about'
import { prime_codes } from '@helpers/corporations/leadership'

describe('corporation About helpers', () => {
    it('rounds shares so a card always adds up to 100', () => {
        expect(percent_shares([1, 1, 1])).toEqual([34, 33, 33])
        expect(percent_shares([0, 0])).toEqual([0, 0])
    })

    it('keeps the given order, drops empty rows and shades by position', () => {
        const rows = mix_rows(
            [{ key: 'regular', count: 28 }, { key: 'core', count: 45 }, { key: 'lapsing', count: 0 }],
            ['core', 'regular', 'lapsing', 'inactive'],
        )
        expect(rows.map((row) => [row.key, row.percent, row.shade])).toEqual([['core', 62, 0], ['regular', 38, 1]])
    })

    it('ranks rows largest first so the headline is the first row', () => {
        const rows = ranked_mix_rows(
            [{ key: 'solo', count: 4 }, { key: 'small_gang', count: 17 }, { key: 'fleet', count: 14 }],
            ['small_gang', 'fleet', 'solo'],
        )
        expect(rows[0].key).toBe('small_gang')
        expect(rows.map((row) => row.shade)).toEqual([0, 1, 2])
    })

    it('scales heatmap levels against the busiest hour', () => {
        const heatmap = Array.from({ length: 7 }, () => Array(24).fill(0))
        heatmap[5][14] = 100
        heatmap[1][17] = 50
        heatmap[0][3] = 1
        const cells = heatmap_cells(heatmap)
        expect(cells[5][14].level).toBe(4)
        expect(cells[1][17].level).toBe(3)
        expect(cells[0][3].level).toBe(1)
        expect(cells[2][0].level).toBe(0)
        expect(busiest_hours(heatmap)).toEqual({ day: 5, hour: 14 })
    })

    it('splits a prime-time window that crosses midnight', () => {
        expect(prime_spans([
            { zone: 'EU', start_hour: 16, end_hour: 20, pilots: 74 },
            { zone: 'US', start_hour: 22, end_hour: 2, pilots: 33 },
        ])).toEqual([
            { zone: 'EU', pilots: 74, column_start: 17, column_end: 21, labelled: true },
            { zone: 'US', pilots: 33, column_start: 23, column_end: 25, labelled: true },
            { zone: 'US', pilots: 33, column_start: 1, column_end: 3, labelled: false },
        ])
    })

    it('reads tenure in the largest sensible unit', () => {
        expect(tenure_parts(590)).toEqual({ value: '1.6', unit: 'years' })
        expect(tenure_parts(240)).toEqual({ value: '8', unit: 'months' })
        expect(tenure_parts(20)).toEqual({ value: '3', unit: 'weeks' })
        expect(tenure_parts(null)).toBeNull()
    })

    it('labels months in the page language', () => {
        expect(month_label('2026-08')).toBe('August 2026')
    })

    it('folds fleet-time buckets into three recruit-facing zones', () => {
        expect(prime_codes({ prime_time: null, observed_prime_times: ['EU', 'AP', 'EU_US'] })).toEqual(['EU', 'AU', 'US'])
        expect(prime_codes({ prime_time: 'AP', observed_prime_times: [] })).toEqual(['AU'])
    })
})
