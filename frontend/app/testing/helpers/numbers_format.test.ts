import { describe, expect, it } from 'vitest'

import { format_hours, format_volume_m3 } from '@helpers/numbers'

describe('format_volume_m3', () => {
    it('returns 0 for zero or non-finite', () => {
        expect(format_volume_m3(0)).toBe('0')
        expect(format_volume_m3(Number.NaN)).toBe('0')
    })

    it('compacts large volumes', () => {
        expect(format_volume_m3(1_500_000)).toBe('1.5M')
        expect(format_volume_m3(21_000)).toBe('21k')
    })
})

describe('format_hours', () => {
    it('keeps a single decimal when needed', () => {
        expect(format_hours(0.34)).toBe('0.3')
        expect(format_hours(1.25)).toBe('1.3')
    })

    it('drops trailing .0 for whole hours', () => {
        expect(format_hours(21)).toBe('21')
    })

    it('returns 0 for non-finite', () => {
        expect(format_hours(Number.NaN)).toBe('0')
    })
})
