import { describe, expect, it } from 'vitest'

import type { AcademyGraduationPilot } from '@dtypes/api.minmatar.org'
import {
    fill,
    group_pilots,
    parse_review_form,
    pipeline_tsv,
    reason_label,
    review_target,
    timeline_dots,
    timezone_label,
    timezone_tokens,
} from '@helpers/corporations/graduation'

function pilot(fields: Partial<AcademyGraduationPilot>): AcademyGraduationPilot {
    return {
        user_id: 1,
        character_id: 1,
        character_name: 'Pilot',
        prime_time: 'US',
        joined_at: null,
        join_estimated: false,
        days_in_academy: 10,
        skill_points: null,
        fleets_90d: 0,
        fleets_30d: 0,
        kills_90d: 0,
        kills_30d: 0,
        small_gang_kills: 0,
        medium_gang_kills: 0,
        large_gang_kills: 0,
        voice_hours_90d: 0,
        ready: false,
        inactive: false,
        stage: 'training',
        suggestions: [],
        last_review: null,
        ...fields,
    }
}

describe('group_pilots', () => {
    it('puts pilots in their column and drops released ones', () => {
        const board = group_pilots([
            pilot({ character_id: 1, stage: 'due' }),
            pilot({ character_id: 2, stage: 'training', days_in_academy: 20 }),
            pilot({ character_id: 3, stage: 'training', days_in_academy: 170 }),
            pilot({ character_id: 4, stage: 'kept' }),
            pilot({ character_id: 5, stage: 'graduating' }),
            pilot({ character_id: 6, stage: 'released' }),
        ])
        expect(board.due.map((p) => p.character_id)).toEqual([1])
        // Next to reach the review first.
        expect(board.training.map((p) => p.character_id)).toEqual([3, 2])
        expect(board.kept.map((p) => p.character_id)).toEqual([4])
        expect(board.graduating.map((p) => p.character_id)).toEqual([5])
    })
})

describe('timezones', () => {
    it('splits combined prime times', () => {
        expect(timezone_tokens('EU_US')).toEqual(['EU', 'US'])
        expect(timezone_tokens(null)).toEqual([])
        expect(timezone_label('AP_EU', 'None')).toBe('AP/EU')
        expect(timezone_label('', 'None')).toBe('None')
    })
})

describe('timeline_dots', () => {
    it('stacks pilots in the same bin and caps the axis', () => {
        const dots = timeline_dots([
            pilot({ character_id: 1, days_in_academy: 181, ready: true }),
            pilot({ character_id: 2, days_in_academy: 184 }),
            pilot({ character_id: 3, days_in_academy: 2000, inactive: true }),
        ])
        const by_id = Object.fromEntries(dots.map((dot) => [dot.character_id, dot]))
        expect(by_id[2].stack).toBe(0)
        expect(by_id[1].stack).toBe(1)
        expect(by_id[1].tone).toBe('ready')
        expect(by_id[3].tone).toBe('inactive')
        expect(by_id[3].left).toBeLessThan(100)
        expect(by_id[3].days).toBe(2000)
    })
})

describe('review_target', () => {
    const pilots = [
        pilot({ character_id: 1, stage: 'due' }),
        pilot({ character_id: 2, stage: 'due' }),
        pilot({ character_id: 3, stage: 'kept' }),
    ]

    it('starts at the head of the queue', () => {
        const target = review_target(pilots)
        expect(target.pilot?.character_id).toBe(1)
        expect(target.position).toBe(1)
        expect(target.total).toBe(2)
        expect(target.next?.character_id).toBe(2)
    })

    it('opens a kept pilot outside the queue', () => {
        const target = review_target(pilots, 3)
        expect(target.pilot?.character_id).toBe(3)
        expect(target.position).toBeNull()
        expect(target.next?.character_id).toBe(1)
    })

    it('has nothing when the queue is empty', () => {
        expect(review_target([]).pilot).toBeNull()
    })
})

describe('parse_review_form', () => {
    function form(fields: Record<string, string>) {
        const data = new FormData()
        for (const [key, value] of Object.entries(fields)) data.set(key, value)
        return data
    }

    it('needs a corporation to graduate', () => {
        expect(parse_review_form(form({ character_id: '7', decision: 'graduate' }))).toBeNull()
        expect(parse_review_form(form({ character_id: '7', decision: 'graduate', corporation_id: '98726134', note: 'ok' })))
            .toEqual({ character_id: 7, decision: 'graduate', corporation_ids: [98726134], note: 'ok' })
    })

    it('ignores the corporation for keep and release', () => {
        expect(parse_review_form(form({ character_id: '7', decision: 'keep', corporation_id: '1' })))
            .toEqual({ character_id: 7, decision: 'keep', corporation_ids: [], note: '' })
    })

    it('rejects unknown decisions', () => {
        expect(parse_review_form(form({ character_id: '7', decision: 'promote' }))).toBeNull()
        expect(parse_review_form(form({ decision: 'keep' }))).toBeNull()
    })
})

describe('reason_label', () => {
    it('falls back for an unknown reason', () => {
        expect(reason_label('large_gang')).toBe('corporations.graduation.reason.large_gang')
        expect(reason_label('new_reason')).toBe('corporations.graduation.reason.all_timezones')
    })
})

describe('fill and pipeline_tsv', () => {
    it('fills placeholders and leaves unknown ones', () => {
        expect(fill('{a} of {b} {c}', { a: 1, b: 'two' })).toBe('1 of two {c}')
    })

    it('writes one row per pilot under a header', () => {
        const tsv = pipeline_tsv([pilot({ character_name: 'Tab\tName', skill_points: 39_400_000, ready: true, suggestions: [{ corporation_id: 1, ticker: 'A-RAT', reason: 'large_gang' }] })])
        const [header, row] = tsv.split('\n')
        expect(header.split('\t')[0]).toBe('Pilot')
        expect(row.split('\t')).toEqual(['Tab Name', 'US', '10', '39', '0', '0', '0', '0', 'yes', 'A-RAT', 'training'])
    })
})
