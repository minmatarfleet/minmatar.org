import { describe, expect, it } from 'vitest'

import { has_changes, word_diff } from '@helpers/word_diff'

const side = (parts: ReturnType<typeof word_diff>, drop: 'add' | 'del') =>
    parts.filter((part) => part.kind !== drop).map((part) => part.text).join('')

describe('word_diff', () => {
    it('marks an added phrase and keeps the rest', () => {
        const parts = word_diff('Join the Rat', 'Join the Rat (now with cake)')
        expect(parts).toEqual([
            { kind: 'same', text: 'Join the Rat' },
            { kind: 'add', text: ' (now with cake)' },
        ])
    })

    it('rebuilds both texts from the parts', () => {
        const before = 'We fly together.\n\nFree ships for new pilots.'
        const after = 'We fly together.\n\nFree ships for all new pilots.\n\nNow with cake.'
        const parts = word_diff(before, after)
        expect(side(parts, 'add')).toBe(before)
        expect(side(parts, 'del')).toBe(after)
        expect(has_changes(parts)).toBe(true)
    })

    it('groups a replaced run as one deletion then one addition', () => {
        const parts = word_diff('fly with the rats today', 'fly with big cats today')
        expect(parts).toEqual([
            { kind: 'same', text: 'fly with ' },
            { kind: 'del', text: 'the rats' },
            { kind: 'add', text: 'big cats' },
            { kind: 'same', text: ' today' },
        ])
    })

    it('reports no change for equal texts', () => {
        const parts = word_diff('same words', 'same words')
        expect(parts).toEqual([{ kind: 'same', text: 'same words' }])
        expect(has_changes(parts)).toBe(false)
    })

    it('handles empty sides', () => {
        expect(word_diff('', 'new')).toEqual([{ kind: 'add', text: 'new' }])
        expect(word_diff('old', '')).toEqual([{ kind: 'del', text: 'old' }])
    })
})
