import { experimental_AstroContainer as AstroContainer } from 'astro/container'
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { describe, expect, test, vi } from 'vitest'

import {
    VIEWER_SOURCES,
    resolve_viewer_path,
    resolve_viewer_target,
    viewer_client_routes,
    viewer_path_table,
} from '@helpers/content_viewer_sources'
import * as warzone from '@/data/warzone'
import * as market from '@/data/amamake-market'
import * as newsletter from '@/data/newsletter'
import { getIndexedGuides, getGuideBySlug } from '@/data/guides'
import { guidePath } from '@/data/guides/urls'

vi.mock('@helpers/fetching/posts', () => ({
    fetch_post_access: vi.fn(async (post_id: number) => post_id === 275
        ? {
            post: {
                post_id: 275,
                state: 'published',
                title: 'The Cope',
                slug: 'the-cope',
                content: '![image](https://example.com/poster.png)',
                date_posted: '2026-10-01T00:00:00Z',
                author: { character_id: 1, character_name: 'BearThatCares' },
                tags: [],
            },
            restricted: null,
        }
        : { post: null, restricted: post_id === 9 ? { reason: 'members' } : null }),
}))

// The market report's volume table loads from the API, on its page as here.
vi.mock('@helpers/api.minmatar.org/market', async (importOriginal) => ({
    ...(await importOriginal<object>()),
    get_inferred_sales_monthly_types: vi.fn(async () => { throw new Error('offline') }),
}))

import ContentViewerLink from '@components/blocks/ContentViewerLink.astro'
import ContentViewerPartial from '@/pages/partials/content_viewer_component.astro'

const t = (key: string) => key

async function render_partial(query: string): Promise<string> {
    const container = await AstroContainer.create()
    return container.renderToString(ContentViewerPartial, {
        request: new Request(`https://my.minmatar.org/partials/content_viewer_component/?${query}`),
    })
}

const attr = (html: string, name: string) => html.match(new RegExp(`${name}="([^"]*)"`))?.[1]
    ?.replaceAll('&#38;', '&').replaceAll('&amp;', '&')

describe('viewable paths', () => {
    test('every source but posts has its pages in the table', () => {
        const sources = new Set([...viewer_path_table().values()].map((target) => target.source))
        expect([...sources].sort()).toEqual(VIEWER_SOURCES.filter((source) => source !== 'post').sort())
    })

    test('issue pages and index pages open their issue', () => {
        const latest_warzone = warzone.get_latest_issue()
        expect(resolve_viewer_path('/warzone/')).toEqual({ source: 'warzone', id: latest_warzone.slug })
        for (const issue of warzone.ISSUES) {
            expect(resolve_viewer_path(issue.permalink_path)).toEqual({ source: 'warzone', id: issue.slug })
        }
        expect(resolve_viewer_path('/amamake-market/')).toEqual({ source: 'market', id: market.get_latest_issue().slug })
        expect(resolve_viewer_path('/newsletter/')).toEqual({ source: 'newsletter', id: newsletter.get_latest_issue().slug })
        expect(resolve_viewer_path('/alliance/values/')).toEqual({ source: 'values', id: '' })
        expect(resolve_viewer_path('/alliance/story/')?.source).toBe('story')
        expect(resolve_viewer_path('/alliance/story/chapter-3/')).toEqual({ source: 'story', id: 'chapter-3' })
    })

    test('every guide with markdown is viewable', () => {
        for (const guide of getIndexedGuides().filter((g) => getGuideBySlug(g.slug))) {
            expect(resolve_viewer_path(guidePath(guide.slug))).toEqual({ source: 'guide', id: guide.slug })
        }
    })

    test('posts match by id, with or without the slug', () => {
        expect(resolve_viewer_path('/alliance/propaganda/the-cope-275')).toEqual({ source: 'post', id: '275' })
        expect(resolve_viewer_path('/alliance/propaganda/275/')).toEqual({ source: 'post', id: '275' })
    })

    test('a missing slash, a query, a hash and a language prefix still match', () => {
        expect(resolve_viewer_path('/alliance/values')?.source).toBe('values')
        expect(resolve_viewer_path('/alliance/values/?x=1#build-relationships')?.source).toBe('values')
        expect(resolve_viewer_path('https://my.minmatar.org/alliance/values/')?.source).toBe('values')
        expect(resolve_viewer_path('/es/alliance/values/', ['en', 'es'])?.source).toBe('values')
    })

    test('other pages are not viewable', () => {
        expect(resolve_viewer_path('/alliance/content/')).toBeNull()
        expect(resolve_viewer_path('/warzone/not-an-issue/')).toBeNull()
        expect(resolve_viewer_path('/fleets/')).toBeNull()
    })

    test('the client gets the same table', () => {
        const routes = viewer_client_routes()
        expect(routes.paths).toEqual([...viewer_path_table().keys()])
        expect(new RegExp(routes.post).test('/alliance/propaganda/the-cope-275')).toBe(true)
    })
})

describe('resolving a target', () => {
    test('each source resolves its title, page and width', async () => {
        const issue = warzone.get_latest_issue()
        await expect(resolve_viewer_target({ source: 'warzone', id: issue.slug }, { t })).resolves.toMatchObject({
            status: 'ok', page_path: issue.permalink_path, width: 'wide',
        })
        await expect(resolve_viewer_target({ source: 'values', id: '' }, { t })).resolves.toMatchObject({
            status: 'ok', title: 'Our values', width: 'reading',
        })
        await expect(resolve_viewer_target({ source: 'story', id: 'chapter-1' }, { t })).resolves.toMatchObject({
            status: 'ok', page_path: '/alliance/story/chapter-1/',
        })
    })

    test('an unknown id is not found, with the page to go to instead', async () => {
        await expect(resolve_viewer_target({ source: 'newsletter', id: 'nope' }, { t })).resolves.toEqual({
            status: 'not_found', page_path: '/newsletter/',
        })
    })

    test('a post is classified; a restricted one is members only', async () => {
        await expect(resolve_viewer_target({ source: 'post', id: '275' }, { t })).resolves.toMatchObject({
            status: 'ok', kind: 'image', width: 'fit', page_path: '/alliance/propaganda/the-cope-275',
        })
        await expect(resolve_viewer_target({ source: 'post', id: '9' }, { t })).resolves.toMatchObject({ status: 'members_only' })
    })
})

describe('the partial', () => {
    test.each([
        ['source=warzone&id=' + warzone.get_latest_issue().slug, 'warzone', 'wide'],
        ['source=market&id=' + market.get_latest_issue().slug, 'market', 'wide'],
        ['source=newsletter&id=' + newsletter.get_latest_issue().slug, 'newsletter', 'wide'],
        ['source=values&id=', 'values', 'reading'],
        ['source=story&id=chapter-2', 'story', 'wide'],
        ['path=%2Falliance%2Fvalues%2F', 'values', 'reading'],
        ['post=275', 'post', 'fit'],
    ])('?%s renders the %s body', async (query, source, width) => {
        const html = await render_partial(query)
        expect(attr(html, 'data-source')).toBe(source)
        expect(attr(html, 'data-width')).toBe(width)
        expect(attr(html, 'data-title')).not.toBe('')
        expect(html).not.toContain('content_viewer.not_found')
    })

    test('a guide renders in a reading column', async () => {
        const guide = getIndexedGuides().find((g) => getGuideBySlug(g.slug))!
        const html = await render_partial(`guide=${guide.slug}`)
        expect(attr(html, 'data-source')).toBe('guide')
        expect(attr(html, 'data-href')).toBe(guidePath(guide.slug))
    })

    test('an unknown page says so and links the page', async () => {
        const html = await render_partial('source=warzone&id=nope')
        expect(attr(html, 'data-kind')).toBe('missing')
        expect(attr(html, 'data-href')).toBe('/warzone/')
    })
})

describe('ContentViewerLink', () => {
    test('a link to a viewable page opens it in the viewer', async () => {
        const container = await AstroContainer.create()
        const html = await container.renderToString(ContentViewerLink, {
            props: { href: '/alliance/values/' },
            slots: { default: 'Our values' },
        })
        expect(attr(html, 'hx-get')).toBe('/partials/content_viewer_component/?source=values&id=')
    })

    test('a link to any other page is a plain link', async () => {
        const container = await AstroContainer.create()
        const html = await container.renderToString(ContentViewerLink, {
            props: { href: '/fleets/' },
            slots: { default: 'Fleets' },
        })
        expect(html).not.toContain('hx-get')
    })
})

// The viewer shows a source by rendering the same body its page renders, so
// the two can't drift. A body has no <script>: the viewer swaps it in with
// htmx, which would not run it.
describe('pages and their bodies', () => {
    const read = (path: string) => readFileSync(join(process.cwd(), path), 'utf8')
    const BODIES: [string, string, string][] = [
        ['warzone', 'src/components/blocks/warzone/WarzoneReportLanding.astro', 'src/components/blocks/warzone/WarzoneReportIssue.astro'],
        ['market', 'src/components/blocks/amamake-market/AmamakeMarketReportLanding.astro', 'src/components/blocks/amamake-market/AmamakeMarketReportIssue.astro'],
        ['newsletter', 'src/components/blocks/newsletter/NewsletterLanding.astro', 'src/components/blocks/newsletter/NewsletterIssue.astro'],
        ['values', 'src/pages/alliance/values.astro', 'src/components/blocks/AllianceValues.astro'],
        ['story', 'src/pages/alliance/story/[chapter_id].astro', 'src/components/blocks/RatChronicle.astro'],
    ]

    test.each(BODIES)('%s: the page renders the body the viewer renders', (_source, page, body) => {
        const file = body.split('/').pop()!
        expect(read(page)).toContain(file)
        expect(read('src/pages/partials/content_viewer_component.astro')).toContain(file)
    })

    test.each(BODIES)('%s: the body has no <script>', (_source, _page, body) => {
        expect(read(body)).not.toMatch(/<script[\s>]/)
    })
})
