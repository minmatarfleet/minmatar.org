import { describe, expect, it } from 'vitest'

import {
    bracket_region,
    timezone_hours,
    timezone_matches,
    timezone_rank,
    timezone_regions,
} from '@helpers/timezones'

describe('timezone helpers', () => {
    it('maps brackets to their region', () => {
        expect(bracket_region('USTZ+')).toBe('US')
        expect(bracket_region('AUTZ')).toBe('AU')
        expect(bracket_region('XX')).toBeNull()
    })

    it('lists each region once in US, EU, AU order', () => {
        expect(timezone_regions({ brackets: ['AUTZ', 'EUTZ+', 'EUTZ'] })).toEqual(['EU', 'AU'])
        expect(timezone_regions(null)).toEqual([])
    })

    it('ranks by the earliest bracket, nothing known last', () => {
        const us_late = timezone_rank({ brackets: ['USTZ+'] })
        const eu = timezone_rank({ brackets: ['AUTZ', 'EUTZ'] })
        const none = timezone_rank({ brackets: [] })
        expect(us_late).toBeLessThan(eu)
        expect(eu).toBeLessThan(none)
    })

    it('matches a base filter to its late bracket and none to no brackets', () => {
        expect(timezone_matches({ brackets: ['USTZ+'] }, 'USTZ')).toBe(true)
        expect(timezone_matches({ brackets: ['EUTZ'] }, 'USTZ')).toBe(false)
        expect(timezone_matches({ brackets: [] }, 'none')).toBe(true)
        expect(timezone_matches(undefined, 'none')).toBe(true)
        expect(timezone_matches({ brackets: ['AUTZ'] }, 'none')).toBe(false)
    })

    it('gives a bracket its EVE hours on the date, following daylight saving', () => {
        const winter = new Date(Date.UTC(2026, 10, 13, 12))
        const summer = new Date(Date.UTC(2026, 6, 1, 12))
        expect(timezone_hours('EUTZ', winter)).toBe('17:00–22:00')
        expect(timezone_hours('EUTZ+', winter)).toBe('22:00–02:00')
        expect(timezone_hours('EUTZ', summer)).toBe('16:00–21:00')
        expect(timezone_hours('USTZ', winter)).toBe('23:00–04:00')
        expect(timezone_hours('AUTZ', winter)).toBe('07:00–12:00')
        expect(timezone_hours('EUTZ', new Date(Date.UTC(2026, 10, 13, 12, 30, 45, 500)))).toBe('17:00–22:00')
        expect(timezone_hours('XX', winter)).toBe('')
    })
})
