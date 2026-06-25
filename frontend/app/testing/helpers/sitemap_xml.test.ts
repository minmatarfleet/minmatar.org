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
                slug: 'guides',
                path: '/guides/',
                publish: true,
            }),
        ).toBe(true)
    })

    it('includes guides and public pages in sitemap paths', () => {
        const paths = getPublicSitemapPagePaths()

        expect(paths).toContain('/guides/')
        expect(paths).toContain('/guides/faction-warfare-advantage/')
        expect(paths).toContain('/guides/navy-destroyer-metagame/')
        expect(paths).not.toContain('/account/')
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
