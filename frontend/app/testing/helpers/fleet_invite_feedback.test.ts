import { describe, expect, it } from 'vitest'

import { answers_from_form, bar_max, bar_width } from '@helpers/fleet_invite_feedback'

describe('answers_from_form', () => {
    it('reads one answer per question and every ticked improvement', () => {
        const form = new FormData()
        form.set('felt', 'fine')
        form.set('sitting_out', 'normal')
        form.set('why', 'other')
        form.set('why_text', 'The two buttons looked the same.')
        form.append('improve', 'lighter')
        form.append('improve', 'why_picked')
        form.set('comment', 'Tell me the doctrine.')

        expect(answers_from_form(form)).toEqual({
            felt: 'fine',
            sitting_out: 'normal',
            why: 'other',
            why_text: 'The two buttons looked the same.',
            improve: ['lighter', 'why_picked'],
            comment: 'Tell me the doctrine.',
        })
    })

    it('leaves a skipped question empty', () => {
        expect(answers_from_form(new FormData()).improve).toEqual([])
        expect(answers_from_form(new FormData()).felt).toBe('')
    })
})

describe('bar_width', () => {
    it('scales each bar to the largest count', () => {
        expect(bar_max([{ key: 'a', label: 'A', count: 4 }, { key: 'b', label: 'B', count: 8 }])).toBe(8)
        expect(bar_width(8, 8)).toBe('100%')
        expect(bar_width(4, 8)).toBe('50%')
        expect(bar_width(0, 0)).toBe('0%')
    })
})
