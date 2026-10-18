import { afterAll, beforeAll, describe, expect, it } from 'vitest'

import { eve_clock, eve_day, eve_day_short } from '@helpers/date'
import { eve_clock as schedule_eve_clock, eve_day as schedule_eve_day } from '@helpers/fetching/fleet_schedule'

// EVE time is UTC: run in a zone where local time is a different day.
const original_tz = process.env.TZ
beforeAll(() => { process.env.TZ = 'Pacific/Kiritimati' })
afterAll(() => { process.env.TZ = original_tz })

const SAMPLES = [
    '2026-10-17T23:30:00Z',
    '2026-01-01T00:05:00Z',
    '2026-02-28T12:00:00Z',
    '2026-10-12',
]

describe('EVE-time helpers', () => {
    it('run in a non-UTC zone during this test', () => {
        expect(new Date('2026-10-17T23:30:00Z').getDate()).toBe(18)
    })

    it('eve_day_short matches the inline month/day format it replaced', () => {
        for (const lang of ['en', 'es', 'de', 'zh']) {
            for (const value of SAMPLES) {
                expect(eve_day_short(lang, value)).toBe(
                    new Date(value).toLocaleDateString(lang, { month: 'short', day: 'numeric', timeZone: 'UTC' }),
                )
                expect(eve_day_short(lang, value, { weekday: true })).toBe(
                    new Date(value).toLocaleDateString(lang, { weekday: 'short', day: 'numeric', month: 'short', timeZone: 'UTC' }),
                )
            }
        }
        expect(eve_day_short('en', '2026-10-17T23:30:00Z')).toBe('Oct 17')
        expect(eve_day_short('en', '2026-10-17T23:30:00Z', { weekday: true })).toBe('Sat, Oct 17')
    })

    it('eve_clock and eve_day read UTC, not local time', () => {
        expect(eve_clock('2026-10-17T23:30:00Z')).toBe('23:30')
        expect(eve_day('2026-10-17T23:30:00Z')).toBe('2026-10-17')
        expect(eve_clock(new Date(Date.UTC(2026, 0, 1, 0, 5)))).toBe('00:05')
    })

    it('fleet_schedule keeps exporting the same functions', () => {
        expect(schedule_eve_clock).toBe(eve_clock)
        expect(schedule_eve_day).toBe(eve_day)
    })
})
