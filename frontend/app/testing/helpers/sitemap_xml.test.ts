import { describe, expect, it } from 'vitest'

import {
    buildSitemapIndexXml,
    buildUrlsetXml,
    escapeXml,
    getPublicSitemapPagePaths,
    isPublicCrawlablePage,
} from '@helpers/sitemap_xml'

describe('sitemap_xml', () => {
    it('escapes XML special characters', () => {
        expect(escapeXml(`Tom & Jerry's "ship"`)).toBe(
            'Tom &amp; Jerry&apos;s &quot;ship&quot;',
        )
    })

    it('excludes auth-gated pages from crawlable set', () => {
        expect(
            isPublicCrawlablePage({
                slug: 'account',
                path: '/account/',
                publish: true,
                permissions: { auth: true },
            }),
        ).toBe(false)

        expect(
            isPublicCrawlablePage({
                slug: 'fleets.upcoming',
                path: '/fleets/upcoming/',
                publish: true,
                permissions: { gate: 'fleets.view' },
            }),
        ).toBe(false)

        expect(
            isPublicCrawlablePage({
                slug: 'guides',
                path: '/guides/',
                publish: true,
            }),
        ).toBe(true)
    })

    it('includes guides and public pages in sitemap paths', () => {
        const paths = getPublicSitemapPagePaths()

        expect(paths).toContain('/guides/')
        expect(paths).toContain('/learning/')
        expect(paths).toContain('/legal/privacy/')
        expect(paths).toContain('/legal/terms/')
        expect(paths).toContain('/learning-center/')
        expect(paths).toContain('/learning/guides/faction-warfare-basics/')
        expect(paths).toContain('/learning/guides/faction-warfare-advantage/')
        expect(paths).toContain('/learning/guides/navy-destroyer-metagame/')
        expect(paths).toContain('/learning/guides/navy-frigate-guide/')
        expect(paths).toContain('/warzone/')
        expect(paths).toContain('/warzone/yc128-07/')
        expect(paths).not.toContain('/guides/faction-warfare-basics/')
        expect(paths).not.toContain('/account/')
    })

    it('lists pages, not the paths that redirect to them', () => {
        const paths = getPublicSitemapPagePaths()

        // Coming-soon guides have a catalog card but no page (404).
        expect(paths).not.toContain('/learning/guides/subcapital-basics/')

        // /campaigns/<slug>/ and /alliance/story/ redirect; the pages live here.
        expect(paths).not.toContain('/campaigns/hek/')
        expect(paths).not.toContain('/campaigns/auga-yc128/')
        expect(paths).toContain('/alliance/campaigns/hek/')
        expect(paths).toContain('/alliance/campaigns/auga-yc128/')
        expect(paths).not.toContain('/alliance/story/')
        expect(paths).toContain('/alliance/story/chapter-1/')
        expect(paths).toContain('/alliance/story/chapter-11/')

        // Filtered views canonicalise to their page, and the newsletter hub to its latest issue.
        expect(paths.filter((path) => path.includes('?'))).toEqual([])
        expect(paths).not.toContain('/newsletter/')
        expect(paths).toContain('/newsletter/yc128-10/')

        // Behind login: anonymous crawlers get the noindex sign-in page.
        expect(paths).not.toContain('/market/buyback/orders/')
    })

    it('keeps pages flagged sitemap: false out', () => {
        expect(
            isPublicCrawlablePage({
                slug: 'alliance.story',
                path: '/alliance/story/',
                publish: true,
                sitemap: false,
            }),
        ).toBe(false)
    })

    it('builds valid urlset and sitemap index XML', () => {
        const urlset = buildUrlsetXml([
            { loc: 'https://my.minmatar.org/guides/', lastmod: '2026-06-25' },
        ])
        expect(urlset).toContain('<urlset')
        expect(urlset).toContain('<loc>https://my.minmatar.org/guides/</loc>')

        const index = buildSitemapIndexXml([
            { loc: 'https://my.minmatar.org/sitemap-pages.xml' },
        ])
        expect(index).toContain('<sitemapindex')
        expect(index).toContain('<loc>https://my.minmatar.org/sitemap-pages.xml</loc>')
    })
})
