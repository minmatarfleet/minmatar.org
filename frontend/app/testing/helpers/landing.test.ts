import { describe, expect, test } from 'vitest'

import type { LandingEvent } from '@dtypes/api.minmatar.org'
import { amount_grade, bar_heights, dedupe_posts, eve_clock, eve_day, event_who, format_number, pick_premium_posts, subject_icon, week_last_column } from '@helpers/landing'

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
    detail: '',
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

    test('amounts grade from muted to the biggest', () => {
        expect(amount_grade('isk', 4_000_000)).toBe(0)
        expect(amount_grade('isk', 352_000_000)).toBe(1)
        expect(amount_grade('isk', 1_600_000_000)).toBe(2)
        expect(amount_grade('isk', 9_200_000_000)).toBe(3)
        expect(amount_grade('lp', 10_000)).toBe(1)
        expect(amount_grade('lp', 52_500)).toBe(3)
    })

    test('industry shows the value made, mining where it happened', () => {
        expect(week_last_column('industry')).toBe('value')
        expect(week_last_column('mining')).toBe('region')
        expect(amount_grade('value', 5_000_000)).toBe(0)
        expect(amount_grade('value', 250_000_000)).toBe(2)
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

describe('pick_premium_posts', () => {
    const post = (title: string, date_posted: string) => ({ title, date_posted })

    test('the newest of each series, whatever order the posts come in', () => {
        const picked = pick_premium_posts([
            post('EVE Online – The Cope – Dread Brawl in Dal', '2026-02-23T00:00:00Z'),
            post('EvE Online - Minmatar Fleet Alliance YC128 In Review', '2026-11-14T00:00:00Z'),
            post('EvE Online - The Cope - The Imperium Retreats', '2026-11-15T00:00:00Z'),
            post('Minmatar Fleet YC127 in review', '2025-11-20T00:00:00Z'),
        ])
        expect(picked.cope?.title).toBe('EvE Online - The Cope - The Imperium Retreats')
        expect(picked.review?.title).toBe('EvE Online - Minmatar Fleet Alliance YC128 In Review')
    })

    test('a series with no post is left out', () => {
        expect(pick_premium_posts([post('The Scope reveals all', '2026-11-01T00:00:00Z'), post('Reviewing doctrines', '2026-11-01T00:00:00Z')])).toEqual({})
    })
})
