import { describe, expect, test } from 'vitest'

import type { LandingEvent } from '@dtypes/api.minmatar.org'
import { bar_heights, dedupe_posts, eve_clock, eve_day, event_who, format_number, short_number, stat_steps, subject_icon } from '@helpers/landing'

const event = (others: number): LandingEvent => ({
    occurred_at: '2026-11-21T17:58:00Z',
    kind: 'kill',
    character_id: 2001,
    character_name: 'Orion Sa-Solo',
    others,
    action: 'fought Snuffed Out and won',
    region: 'Metropolis',
    verb: 'fought',
    subject: 'Snuffed Out',
    subject_type: 'alliance',
    subject_id: 99000001,
    tail: 'and won',
    amount: 0,
})

describe('landing helpers', () => {
    test('event_who names one pilot and counts the rest', () => {
        expect(event_who(event(0), 'and {count} others')).toBe('Orion Sa-Solo')
        expect(event_who(event(8), 'and {count} others')).toBe('Orion Sa-Solo and 8 others')
        expect(event_who(event(1), 'and {count} others', 'and {count} other')).toBe('Orion Sa-Solo and 1 other')
    })

    test('subject icons come from the image server', () => {
        expect(subject_icon({ subject_type: 'type', subject_id: 587 })).toBe('https://images.evetech.net/types/587/icon?size=32')
        expect(subject_icon({ subject_type: 'alliance', subject_id: 99000001 }, 64)).toBe('https://images.evetech.net/alliances/99000001/logo?size=64')
        expect(subject_icon({ subject_type: 'faction', subject_id: 500003 })).toBe('https://images.evetech.net/corporations/1000179/logo?size=32')
        expect(subject_icon({ subject_type: '', subject_id: 0 })).toBeNull()
    })

    test('the 24-hour numbers step up to the totals as lines land', () => {
        const kill = { ...event(0), kind: 'kill', subject_type: 'type' }
        const complex = { ...event(0), kind: 'site', verb: 'captured a complex' }
        const mining = { ...event(0), kind: 'mining', amount: 42000 }
        const totals = { ships_destroyed: 10, warzone_sites: 5, complexes: 2, mined_volume: 100000 }
        const steps = stat_steps(totals, [kill, kill, complex, mining], 1)
        expect(steps[0]).toEqual({ ships_destroyed: 10, warzone_sites: 4, complexes: 1, mined_volume: 58000 })
        expect(steps.at(-1)).toEqual(totals)
        expect(steps).toHaveLength(3)
    })

    test('big numbers are short', () => {
        expect(short_number(17664013)).toBe('17.7M')
        expect(short_number(367680)).toBe('368K')
        expect(short_number(950)).toBe('950')
    })

    test('times are EVE time', () => {
        expect(eve_clock('2026-11-21T17:58:00Z')).toBe('17:58')
        expect(eve_day('2026-11-15T23:30:00Z')).toBe('Sun 15 Nov')
    })

    test('bar heights scale to the tallest bar and keep a stub for zero', () => {
        expect(bar_heights([0, 16, 32])).toEqual([4, 50, 100])
        expect(bar_heights([0, 0])).toEqual([4, 4])
    })

    test('numbers are grouped', () => {
        expect(format_number(1713)).toBe('1,713')
    })
})

describe('dedupe_posts', () => {
    test('a Reddit cross-post collapses into the plain post', () => {
        const posts = [
            { title: 'The Cope - The Imperium Retreats', image: 'a.jpg' },
            { title: 'The Cope - The Imperium Retreats (Reddit)', image: 'a.jpg' },
            { title: 'YC128 In Review (Reddit)', image: 'b.jpg' },
            { title: 'YC128 In Review', image: 'b.jpg' },
            { title: 'Something else', image: 'c.jpg' },
        ]
        expect(dedupe_posts(posts).map((p) => p.title)).toEqual([
            'The Cope - The Imperium Retreats',
            'YC128 In Review',
            'Something else',
        ])
    })

    test('same cover image with a different title is one story', () => {
        expect(dedupe_posts([{ title: 'A', image: 'x.jpg' }, { title: 'B', image: 'x.jpg' }])).toHaveLength(1)
    })
})
