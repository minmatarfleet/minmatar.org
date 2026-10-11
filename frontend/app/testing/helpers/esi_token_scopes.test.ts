import { describe, expect, it } from 'vitest'

import { elevated_scopes_for_token_type } from '@helpers/esi_token_scopes'

describe('elevated_scopes_for_token_type', () => {
    it('returns empty for Basic, blank, or unknown', () => {
        expect(elevated_scopes_for_token_type('Basic')).toEqual([])
        expect(elevated_scopes_for_token_type('')).toEqual([])
        expect(elevated_scopes_for_token_type(null)).toEqual([])
        expect(elevated_scopes_for_token_type('Nope')).toEqual([])
    })

    it('returns Industry scopes beyond Basic', () => {
        const scopes = elevated_scopes_for_token_type('Industry')
        expect(scopes).toContain('esi-industry.read_character_mining.v1')
        expect(scopes).toContain('esi-characters.read_blueprints.v1')
        expect(scopes).not.toContain('esi-skills.read_skills.v1')
    })

    it('returns Market scopes beyond Basic', () => {
        const scopes = elevated_scopes_for_token_type('Market')
        expect(scopes).toContain('esi-markets.structure_markets.v1')
        expect(scopes).toContain('esi-corporations.read_corporation_membership.v1')
        expect(scopes).not.toContain('esi-assets.read_assets.v1')
    })
})
