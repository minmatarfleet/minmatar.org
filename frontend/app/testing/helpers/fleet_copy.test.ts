import { describe, expect, it } from 'vitest'

import {
    copied_alert_content,
    copied_fleet_path,
    copy_default_start,
    copy_start_iso,
    parse_not_copied,
} from '@helpers/fleet_copy'
import { LOCAL_HOUR_BANDS } from '@helpers/local_hour'

const t = (key:string) => `[${key}]`

describe('copy_default_start', () => {
    it('is the same EVE weekday and time one week on', () => {
        const now = new Date('2026-10-23T13:47:27Z')
        expect(copy_default_start('2026-10-20T19:00:00Z', now)).toEqual({ eve_date: '2026-10-27', eve_time: '19:00' })
    })

    it('skips weeks that have already passed', () => {
        const now = new Date('2026-11-12T08:00:00Z')
        expect(copy_default_start('2026-10-20T19:00:00Z', now)).toEqual({ eve_date: '2026-11-17', eve_time: '19:00' })
    })

    it('never lands on now itself', () => {
        const now = new Date('2026-10-27T19:00:00Z')
        expect(copy_default_start('2026-10-20T19:00:00Z', now).eve_date).toBe('2026-11-03')
    })

    it('copies an upcoming fleet to the week after it', () => {
        const now = new Date('2026-10-23T13:47:27Z')
        expect(copy_default_start('2026-10-24T23:30:00Z', now)).toEqual({ eve_date: '2026-10-31', eve_time: '23:30' })
    })
})

describe('copy_start_iso', () => {
    it('reads the fields as EVE (UTC) time', () => {
        expect(copy_start_iso('2026-10-27', '19:00')).toBe('2026-10-27T19:00:00.000Z')
    })

    it('rejects missing or malformed fields', () => {
        expect(copy_start_iso('', '19:00')).toBeNull()
        expect(copy_start_iso('2026-10-27', '')).toBeNull()
        expect(copy_start_iso('27/10/2026', '19:00')).toBeNull()
        expect(copy_start_iso('2026-13-45', '19:00')).toBeNull()
    })
})

describe('not copied settings', () => {
    it('keeps known keys in the alert order', () => {
        expect(parse_not_copied('open_to_alliance,bogus,campaign')).toEqual(['campaign', 'open_to_alliance'])
        expect(parse_not_copied(null)).toEqual([])
        expect(parse_not_copied('')).toEqual([])
    })

    it('puts only known keys on the new fleet URL', () => {
        expect(copied_fleet_path(42, 7, [])).toBe('/fleets/upcoming/42?copied_from=7')
        expect(copied_fleet_path(42, 7, ['location', 'oops'])).toBe('/fleets/upcoming/42?copied_from=7&not_copied=location')
    })

    it('lists each setting left off', () => {
        expect(copied_alert_content([], t)).toBe('<p>[fleets.copy.copied_text]</p>')
        expect(copied_alert_content(['campaign', 'location'], t)).toBe(
            '<p>[fleets.copy.copied_text]</p><p>[fleets.copy.not_copied]</p>' +
            '<ul><li>[fleets.copy.not_copied.campaign]</li><li>[fleets.copy.not_copied.location]</li></ul>',
        )
    })
})

describe('LOCAL_HOUR_BANDS', () => {
    it('matches the hour colours LocalTime always used', () => {
        const expected = (hour:number) =>
            hour < 7 ? ['text-status-point-2', 'sleeptime'] :
            hour < 8 ? ['text-status-point-3', 'sleeptime'] :
            hour < 9 ? ['text-status-point-4', 'daytime'] :
            hour < 19 ? ['text-status-point-5', 'daytime'] :
            hour < 20 ? ['text-status-point-6', 'nighttime'] :
            hour < 21 ? ['text-status-point-7', 'nighttime'] :
            hour < 22 ? ['text-status-point-8', 'nighttime'] :
            hour < 23 ? ['text-status-point-9', 'nighttime'] :
            ['text-status-null', 'sleeptime']

        expect(LOCAL_HOUR_BANDS).toHaveLength(24)
        LOCAL_HOUR_BANDS.forEach((band, hour) => expect([...band]).toEqual(expected(hour)))
    })
})
