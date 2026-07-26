import { describe, expect, it } from 'vitest'

import {
    build_canonical_url,
    get_site_origin,
    is_noindex_path,
} from '@helpers/seo'

describe('seo', () => {
    it('detects noindex paths', () => {
        expect(is_noindex_path('/partials/fitting_finder_component')).toBe(true)
        expect(is_noindex_path('/redirects/auth_init')).toBe(true)
        expect(is_noindex_path('/alliance/')).toBe(false)
    })

    it('builds canonical URLs from translated paths', () => {
        const translatePath = (path: string) => path
        const url = build_canonical_url('/guides/', translatePath, 'http://localhost:4321')

        expect(url).toMatch(/\/guides\/$/)
    })

    it('uses fallback origin outside production', () => {
        expect(get_site_origin('http://localhost:4321')).toBe('http://localhost:4321')
    })
})
