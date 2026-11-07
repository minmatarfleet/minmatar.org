import { describe, expect, it } from 'vitest'

import { format_isk_shorthand, parse_isk_shorthand } from '@helpers/isk_shorthand'

describe('parse_isk_shorthand', () => {
    it('reads the units pilots type', () => {
        expect(parse_isk_shorthand('1.8m')).toBe(1_800_000)
        expect(parse_isk_shorthand('800k')).toBe(800_000)
        expect(parse_isk_shorthand('2B')).toBe(2_000_000_000)
        expect(parse_isk_shorthand(' 1,500,000 ISK ')).toBe(1_500_000)
        expect(parse_isk_shorthand('0')).toBe(0)
    })

    it('refuses what is not an amount', () => {
        expect(parse_isk_shorthand('')).toBeNull()
        expect(parse_isk_shorthand('-5m')).toBeNull()
        expect(parse_isk_shorthand('lots')).toBeNull()
        expect(parse_isk_shorthand('1.2.3m')).toBeNull()
        expect(parse_isk_shorthand(null)).toBeNull()
    })
})

describe('format_isk_shorthand', () => {
    it('writes the shortest exact form', () => {
        expect(format_isk_shorthand(1_800_000)).toBe('1.8M')
        expect(format_isk_shorthand(800_000)).toBe('800k')
        expect(format_isk_shorthand(20_000_000)).toBe('20M')
        expect(format_isk_shorthand(2_500_000_000)).toBe('2.5B')
        expect(format_isk_shorthand(0)).toBe('0')
    })

    it('never rounds: every value parses back to itself', () => {
        for (const value of [12_345_678, 1_234_500, 999, 1_000_001, 7_250_000])
            expect(parse_isk_shorthand(format_isk_shorthand(value))).toBe(value)
        expect(format_isk_shorthand(12_345_678)).toBe('12,345,678')
    })
})
