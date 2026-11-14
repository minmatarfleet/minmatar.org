import { describe, expect, it } from 'vitest'

import {
    countdown_text,
    default_fit_key,
    eve_when_text,
    is_rsvp_token,
    parse_fit_key,
    rsvp_confidence,
    rsvp_intent,
    rsvp_submit_from_form,
} from '@helpers/fleet_rsvp'

const fit = (key: string, ship_id = 1) => ({
    key, name: key, ship_id, ship_name: 'Ship', role: 'dps', fitting_id: null, fleet_fitting_id: null,
})

describe('is_rsvp_token', () => {
    it('takes a Django signed token', () => {
        expect(is_rsvp_token('.eJyrVspUslIyNDBQ0lEqBTENzYwtTA0NLYGsWgBqWgYy:1vJx2a:abcDEF-_123')).toBe(true)
    })

    it('refuses anything that could change the API path', () => {
        expect(is_rsvp_token('..')).toBe(false)
        expect(is_rsvp_token('abcdefghijklmnopqrstuvwxyz/../x')).toBe(false)
        expect(is_rsvp_token('abcdefghijklmnopqrstuvwxyz?x=1')).toBe(false)
        expect(is_rsvp_token('')).toBe(false)
        expect(is_rsvp_token(undefined)).toBe(false)
    })
})

describe('default_fit_key', () => {
    const fits = [fit('f:1'), fit('f:2'), fit('m:3')]

    it('prefers the saved pick, then the usual, then the first fit', () => {
        expect(default_fit_key({ fits, picked_key: 'm:3', suggested_key: 'f:2' })).toBe('m:3')
        expect(default_fit_key({ fits, picked_key: '', suggested_key: 'f:2' })).toBe('f:2')
        expect(default_fit_key({ fits, picked_key: '', suggested_key: '' })).toBe('f:1')
    })

    it('ignores keys the character cannot fly', () => {
        expect(default_fit_key({ fits, picked_key: 'f:9', suggested_key: 'f:8' })).toBe('f:1')
        expect(default_fit_key({ fits: [], picked_key: '', suggested_key: '' })).toBe('')
    })
})

describe('rsvp_submit_from_form', () => {
    it('sends each ticked character with the fit in its select', () => {
        const data = new FormData()
        data.append('confidence', 'medium')
        data.append('character', '11')
        data.append('character', '22')
        data.append('fit_11', 'f:5')
        data.append('fit_22', 'm:7')
        data.append('fit_33', 'f:9') // unticked: its select still posts
        expect(rsvp_submit_from_form(data)).toEqual({
            confidence: 'medium',
            picks: [
                { character_id: 11, fitting_id: 5 },
                { character_id: 22, fleet_fitting_id: 7 },
            ],
        })
    })

    it('sends no picks for a fleet with no doctrine, and defaults to high', () => {
        const data = new FormData()
        data.append('character', '11')
        data.append('confidence', 'certain')
        expect(rsvp_submit_from_form(data)).toEqual({ confidence: 'high', picks: [] })
    })

    it('drops junk and repeated characters', () => {
        const data = new FormData()
        data.append('character', 'x')
        data.append('character', '-4')
        data.append('character', '11')
        data.append('character', '11')
        data.append('fit_11', 'f:5')
        expect(rsvp_submit_from_form(data).picks).toEqual([{ character_id: 11, fitting_id: 5 }])
    })
})

describe('form values', () => {
    it('parses fit keys', () => {
        expect(parse_fit_key('f:12')).toEqual({ fitting_id: 12 })
        expect(parse_fit_key('m:4')).toEqual({ fleet_fitting_id: 4 })
        expect(parse_fit_key('x:4')).toBeNull()
        expect(parse_fit_key('f:')).toBeNull()
    })

    it('reads confidence and intent', () => {
        expect(rsvp_confidence('low')).toBe('low')
        expect(rsvp_confidence('')).toBe('high')
        const data = new FormData()
        expect(rsvp_intent(data)).toBe('sign_up')
        data.append('intent', 'not_available')
        expect(rsvp_intent(data)).toBe('not_available')
    })
})

describe('times', () => {
    it('puts the EVE clock before the EVE day', () => {
        expect(eve_when_text('2026-11-13T19:00:00Z')).toBe('19:00 EVE · Fri 13 Nov')
        // 23:30 UTC is still Friday in EVE whatever the server's zone.
        expect(eve_when_text('2026-11-13T23:30:00Z')).toBe('23:30 EVE · Fri 13 Nov')
    })

    const templates = { days: 'in {d}d {h}h', hours: 'in {h}h {m}m', minutes: 'in {m}m', started: 'Starting now' }

    it('counts down in days, hours or minutes', () => {
        const minute = 60_000
        expect(countdown_text(templates, (2 * 60 + 48) * minute + 30_000)).toBe('in 2h 48m')
        expect(countdown_text(templates, (26 * 60 + 5) * minute)).toBe('in 1d 2h')
        expect(countdown_text(templates, 7 * minute)).toBe('in 7m')
        expect(countdown_text(templates, 0)).toBe('Starting now')
        expect(countdown_text(templates, -minute)).toBe('Starting now')
    })
})
