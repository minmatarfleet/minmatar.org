import type { PageFinderUI, Permissions } from '@dtypes/layout_components'

import sitemap from '@json/sitemap.json'
import { guides } from '@/data/guides'
import { getGuideCanonicalPath } from '@/data/guides/seo'
import { get_prod_url } from '@helpers/env'

export function escapeXml(value: string): string {
    return value
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&apos;')
}

export function getSitemapOrigin(request: Request): string {
    if (import.meta.env.PROD) {
        return get_prod_url().replace(/\/$/, '')
    }
    return new URL(request.url).origin
}

function hasRestrictedPermissions(permissions: Permissions): boolean {
    if (permissions.auth) return true
    if (permissions.group_officer) return true
    if (permissions.team_director) return true
    if (permissions.superuser) return true
    if (permissions.user?.length) return true
    return false
}

export function isPublicCrawlablePage(page: PageFinderUI): boolean {
    if (!page.publish) return false
    if (!page.permissions) return true
    return !hasRestrictedPermissions(page.permissions)
}

export interface SitemapUrlEntry {
    loc: string
    lastmod?: string
}

export function getPublicSitemapPagePaths(): string[] {
    const paths = new Set<string>()

    for (const page of sitemap as PageFinderUI[]) {
        if (!isPublicCrawlablePage(page)) continue
        paths.add(page.path)
    }

    for (const guide of guides) {
        paths.add(getGuideCanonicalPath(guide))
    }

    return [...paths].sort()
}

export function buildUrlsetXml(entries: SitemapUrlEntry[]): string {
    const urlBlocks = entries
        .map(({ loc, lastmod }) => {
            const lastmodXml = lastmod ? `\n    <lastmod>${escapeXml(lastmod)}</lastmod>` : ''
            return `  <url>\n    <loc>${escapeXml(loc)}</loc>${lastmodXml}\n  </url>`
        })
        .join('\n')

    return `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
${urlBlocks}
</urlset>`
}

export function buildSitemapIndexXml(sitemaps: SitemapUrlEntry[]): string {
    const sitemapBlocks = sitemaps
        .map(({ loc, lastmod }) => {
            const lastmodXml = lastmod ? `\n    <lastmod>${escapeXml(lastmod)}</lastmod>` : ''
            return `  <sitemap>\n    <loc>${escapeXml(loc)}</loc>${lastmodXml}\n  </sitemap>`
        })
        .join('\n')

    return `<?xml version="1.0" encoding="UTF-8"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
${sitemapBlocks}
</sitemapindex>`
}

export const XML_RESPONSE_HEADERS = {
    'Content-Type': 'application/xml; charset=utf-8',
} as const
