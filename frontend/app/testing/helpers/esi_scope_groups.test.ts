import { describe, expect, it } from 'vitest'

import {
    chosen_scope_groups,
    requested_scope_count,
    requested_scope_groups,
    scope_groups_cookie_value,
    scope_groups_query,
} from '@helpers/esi_scope_groups'

describe('chosen_scope_groups', () => {
    it('starts from Industry, Market and Desktop when nothing was chosen yet', () => {
        expect(chosen_scope_groups(undefined)).toEqual(['Industry', 'Market', 'Desktop'])
        expect(chosen_scope_groups('')).toEqual(['Industry', 'Market', 'Desktop'])
    })

    it('keeps only optional groups from the cookie', () => {
        expect(chosen_scope_groups('v2:Director,Basic,Executor,Industry')).toEqual(['Industry', 'Director'])
    })

    it('reads the none marker as every optional group off', () => {
        expect(scope_groups_cookie_value([])).toBe('v2:-')
        expect(chosen_scope_groups(scope_groups_cookie_value([]))).toEqual([])
    })

    it('round-trips a choice, Desktop off included', () => {
        expect(chosen_scope_groups(scope_groups_cookie_value(['Market', 'Director']))).toEqual(['Market', 'Director'])
    })

    it('turns Desktop on for cookies written before it existed, keeping their other answers', () => {
        expect(chosen_scope_groups('Industry,Director')).toEqual(['Industry', 'Desktop', 'Director'])
        expect(chosen_scope_groups('-')).toEqual(['Desktop'])
    })
})

describe('requested scope groups', () => {
    it('always sends Faction Warfare and never Basic', () => {
        expect(requested_scope_groups([])).toEqual(['FactionWarfare'])
        expect(requested_scope_groups(['Market', 'Director'])).toEqual(['FactionWarfare', 'Market', 'Director'])
        expect(scope_groups_query(['Industry'])).toBe('&scope_groups=FactionWarfare%2CIndustry')
    })

    it('counts each scope once', () => {
        expect(requested_scope_count([])).toBe(13)
        expect(requested_scope_count(['Industry', 'Market'])).toBe(26)
        expect(requested_scope_count(['Industry', 'Market', 'Director'])).toBe(42)
        expect(requested_scope_count(['Industry', 'Market', 'Desktop'])).toBe(32)
    })
})
