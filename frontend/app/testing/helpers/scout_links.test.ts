import { describe, expect, it } from 'vitest'

import { is_scout_link_target, scout_link_destination } from '@helpers/scout_links'
import { is_noindex_path } from '@helpers/seo'

describe('scout links', () => {
    it('sends Discord to the vanity invite', () => {
        expect(scout_link_destination('discord')).toBe('https://discord.gg/minmatar')
    })

    it('sends site targets to their page', () => {
        expect(scout_link_destination('learning')).toBe('/learning/')
        expect(scout_link_destination('corporations')).toBe('/alliance/corporations/')
        expect(scout_link_destination('warzone')).toBe('/warzone/')
        expect(scout_link_destination('amamake')).toBe('/amamake-market/')
    })

    it('sends unknown targets home without counting them', () => {
        expect(scout_link_destination('https://evil.example')).toBe('/')
        expect(scout_link_destination('toString')).toBe('/')
        expect(is_scout_link_target('toString')).toBe(false)
    })

    it('keeps tracked links out of search results', () => {
        expect(is_noindex_path('/go/k3x9qa/discord')).toBe(true)
    })
})
