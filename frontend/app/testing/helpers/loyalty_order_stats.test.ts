import { describe, expect, it } from 'vitest'
import {
    express_hours_left,
    format_close_time,
    tlf_currency,
} from '../../src/helpers/loyalty_order_stats'

describe('format_close_time', () => {
    it('handles missing values', () => {
        expect(format_close_time(null)).toBe('—')
        expect(format_close_time(undefined)).toBe('—')
    })

    it('formats minutes, hours and days', () => {
        expect(format_close_time(45 * 60)).toBe('45m')
        expect(format_close_time(14 * 3600)).toBe('14h')
        expect(format_close_time(14 * 3600 + 20 * 60)).toBe('14h 20m')
        expect(format_close_time(2 * 86400 + 6 * 3600 + 59)).toBe('2d 6h')
        expect(format_close_time(3 * 86400)).toBe('3d')
    })
})

describe('express_hours_left', () => {
    it('is negative once overdue', () => {
        const now = new Date('2026-10-16T12:00:00Z')
        expect(express_hours_left('2026-10-16T18:00:00Z', now)).toBe(6)
        expect(express_hours_left('2026-10-16T10:30:00Z', now)).toBe(-1.5)
    })
})

describe('tlf_currency', () => {
    const base = {
        default_isk_per_lp: 800,
        express_isk_per_lp: null,
        is_active: true,
        allow_buy: true,
        allow_sell: true,
    }

    it('picks Tribal Liberation Force only', () => {
        const tlf = { ...base, id: 1, name: 'Tribal Liberation Force', corporation_id: 1000182 }
        const other = { ...base, id: 2, name: '24th Imperial Crusade', corporation_id: 1000179 }
        expect(tlf_currency([other, tlf])).toBe(tlf)
        expect(tlf_currency([other])).toBeNull()
    })
})
