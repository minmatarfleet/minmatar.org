import { describe, expect, test } from 'vitest'

import type { LandingEvent } from '@dtypes/api.minmatar.org'
import { bar_heights, dedupe_posts, eve_clock, eve_day, event_who, format_number } from '@helpers/landing'

const event = (others: number): LandingEvent => ({
    occurred_at: '2026-11-21T17:58:00Z',
    kind: 'kill',
    character_id: 2001,
    character_name: 'Orion Sa-Solo',
    others,
    action: 'fought Snuffed Out and won',
    region: 'Metropolis',
})

describe('landing helpers', () => {
    test('event_who names one pilot and counts the rest', () => {
        expect(event_who(event(0), 'and {count} others')).toBe('Orion Sa-Solo')
        expect(event_who(event(8), 'and {count} others')).toBe('Orion Sa-Solo and 8 others')
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
