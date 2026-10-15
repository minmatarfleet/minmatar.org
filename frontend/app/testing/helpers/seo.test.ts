import { describe, expect, it } from 'vitest'

import { useTranslations } from '@i18n/utils'
import {
    build_canonical_url,
    get_site_origin,
    is_auth_init_redirect,
    is_noindex_path,
    page_seo_for_path,
    pathname_from_return_target,
} from '@helpers/seo'

const t = useTranslations('en')

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

    it('uses the sitemap title and meta description for an exact path', () => {
        expect(page_seo_for_path('/fleets/upcoming/', t)).toEqual({
            title: 'Fleets',
            description: t('page_finder.fleets.upcoming.meta_description'),
        })
    })

    it('uses the longest sitemap prefix and ignores the site root', () => {
        expect(page_seo_for_path('/account/referrals/extra', t)?.title).toBe('Referral links')
        expect(page_seo_for_path('/not-a-real-page/child/', t)).toBeNull()
    })

    it('uses the fleet id title for fleet detail paths', () => {
        expect(page_seo_for_path('/fleets/upcoming/42', t)).toEqual({
            title: 'Fleet 42',
            description: t('page_finder.fleets.upcoming.meta_description'),
        })
        expect(page_seo_for_path('/fleets/history/7/', t)).toEqual({
            title: 'Fleet 7',
            description: t('page_finder.fleets.history.description'),
        })
    })

    it('reads a same-origin return path and detects the login redirect', () => {
        expect(pathname_from_return_target(
            'https://my.minmatar.org/fleets/upcoming/?x=1',
            'https://my.minmatar.org',
        )).toBe('/fleets/upcoming/')
        expect(pathname_from_return_target(
            'https://evil.example/fleets/upcoming/',
            'https://my.minmatar.org',
        )).toBeNull()
        expect(is_auth_init_redirect(
            '/redirects/auth_init?redirect_url=%2Ffleets%2Fupcoming%2F',
            'https://my.minmatar.org',
        )).toBe(true)
        expect(is_auth_init_redirect('/account/', 'https://my.minmatar.org')).toBe(false)
    })
})
