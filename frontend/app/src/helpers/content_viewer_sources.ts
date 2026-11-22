/**
 * ContentViewer sources: every kind of page the viewer can show in place.
 *
 * A source is a page split in two: the page route renders its own frame
 * (Viewport, cover, hero, SEO) around a body component, and the viewer's
 * partial renders the same body inside the viewer. This file says which page
 * paths are viewable, what each one resolves to, and how wide the viewer opens
 * for it. The body component for each source is in the partial
 * (`src/pages/partials/content_viewer_component.astro`), typed so a source
 * without one fails `astro check`.
 *
 * To make a page viewable: give it a body component the page route renders,
 * add a source here, and add its body to the partial.
 */

import { t_key } from '@helpers/i18n'
import type { TranslationKey } from '@i18n/utils'
import { fetch_post_access } from '@helpers/fetching/posts'
import { classify_post, post_page_path } from '@helpers/content_viewer'
import type { ViewerPost } from '@helpers/content_viewer'
import type { PostUI } from '@dtypes/layout_components'

import { guides, getGuideBySlug } from '@/data/guides'
import { guidePath } from '@/data/guides/urls'
import * as warzone from '@/data/warzone'
import type { WarzoneIssue } from '@/data/warzone/types'
import * as market from '@/data/amamake-market'
import type { AmamakeMarketIssue } from '@/data/amamake-market/types'
import * as newsletter from '@/data/newsletter'
import type { NewsletterIssue } from '@/data/newsletter/types'
import { ratChronicleChapters, getChronicleChapterById, defaultChronicleChapterId } from '@/data/rat-chronicle'
import * as values_page from '@markdown/values.md'
import * as story_page from '@markdown/story.md'

export const VIEWER_SOURCES = ['post', 'guide', 'warzone', 'market', 'newsletter', 'values', 'story'] as const
export type ViewerSource = (typeof VIEWER_SOURCES)[number]

/**
 * How wide the viewer opens: `wide` for reports and videos, `reading` for a
 * column of text, `fit` for a poster or gallery, `narrow` for a message.
 */
export type ViewerWidth = 'wide' | 'reading' | 'fit' | 'narrow'

export interface ViewerTarget {
    source: ViewerSource
    id: string
}

/** What each source's body component is given. */
export interface ViewerBodyProps {
    post: { post: PostUI, view: ViewerPost }
    guide: { slug: string }
    warzone: { issue: WarzoneIssue }
    market: { issue: AmamakeMarketIssue }
    newsletter: { issue: NewsletterIssue }
    values: Record<string, never>
    story: { chapter_id: string }
}

export type ViewerResolved = {
    [S in ViewerSource]: {
        status: 'ok'
        source: S
        title: string
        /** The full page, untranslated. */
        page_path: string
        width: ViewerWidth
        /** Finer than the width, for a post: video, image, gallery or article. */
        kind: string
        props: ViewerBodyProps[S]
    }
}[ViewerSource]

export type ViewerMissing =
    | { status: 'not_found', page_path: string }
    | { status: 'members_only', page_path: string }
    | { status: 'error', page_path: string, error: Error }

export interface ViewerContext {
    t: (key: TranslationKey) => string
    auth_token?: string | false | null
}

// Posts are the only source without a fixed list: any id, with or without its slug.
const POST_PATH = /^\/alliance\/propaganda\/(?:[^/]*-)?(\d+)\/?$/

function with_slash(path: string): string {
    return path.endsWith('/') ? path : `${path}/`
}

let path_table: Map<string, ViewerTarget> | null = null

/**
 * Every viewable page path (with a trailing slash, no language prefix) and
 * what it opens. An index route such as `/warzone/` opens its latest issue.
 */
export function viewer_path_table(): Map<string, ViewerTarget> {
    if (path_table) return path_table
    const table = new Map<string, ViewerTarget>()
    const add = (path: string, source: ViewerSource, id: string) => table.set(with_slash(path), { source, id })

    for (const guide of guides) {
        if (getGuideBySlug(guide.slug)) add(guidePath(guide.slug), 'guide', guide.slug)
    }

    add('/warzone/', 'warzone', warzone.get_latest_issue().slug)
    for (const issue of warzone.ISSUES) add(issue.permalink_path, 'warzone', issue.slug)

    add(market.LATEST_PATH, 'market', market.get_latest_issue().slug)
    for (const issue of market.ISSUES) add(issue.permalink_path, 'market', issue.slug)

    add('/newsletter/', 'newsletter', newsletter.get_latest_issue().slug)
    for (const issue of newsletter.ISSUES) add(issue.permalink_path, 'newsletter', issue.slug)

    add('/alliance/values/', 'values', '')

    add('/alliance/story/', 'story', defaultChronicleChapterId)
    for (const chapter of ratChronicleChapters) add(`/alliance/story/${chapter.id}/`, 'story', chapter.id)

    path_table = table
    return table
}

/** The path without its language prefix (`/es/warzone/` → `/warzone/`). */
export function strip_lang(path: string, languages: readonly string[]): string {
    const [, first, ...rest] = path.split('/')
    return languages.includes(first) ? `/${rest.join('/')}` : path
}

/**
 * What a link to `href` opens in the viewer, or null when it is not a
 * viewable page (the link then just navigates). Ignores query and hash.
 */
export function resolve_viewer_path(href: string, languages: readonly string[] = []): ViewerTarget | null {
    let path: string
    try {
        path = new URL(href, 'https://my.minmatar.org').pathname
    } catch {
        return null
    }
    path = strip_lang(path, languages)

    const post = path.match(POST_PATH)
    if (post) return { source: 'post', id: post[1] }

    return viewer_path_table().get(with_slash(path)) ?? null
}

/**
 * The patterns the client checks a clicked link against, so a link inside the
 * viewer to another viewable page opens in the viewer too.
 */
export function viewer_client_routes(): { paths: string[], post: string } {
    return { paths: [...viewer_path_table().keys()], post: POST_PATH.source }
}

/** The partial's query for a target. */
export function viewer_query(target: ViewerTarget): string {
    return `source=${target.source}&id=${encodeURIComponent(target.id)}`
}

const underscored = (slug: string) => slug.replaceAll('-', '_')

/** Loads what a target shows: its title, full page, width and body props. */
export async function resolve_viewer_target(
    target: ViewerTarget,
    { t, auth_token }: ViewerContext,
): Promise<ViewerResolved | ViewerMissing> {
    const { source, id } = target

    if (source === 'post') {
        const post_id = parseInt(id)
        const page_path = post_page_path({ post_id })
        if (isNaN(post_id)) return { status: 'not_found', page_path }
        let access
        try {
            access = await fetch_post_access(post_id, auth_token)
        } catch (error) {
            return { status: 'error', page_path, error: error instanceof Error ? error : new Error(String(error)) }
        }
        const post = access.post?.state === 'published' ? access.post : null
        if (!post) return { status: access.restricted ? 'members_only' : 'not_found', page_path }
        const view = classify_post(post.content ?? '')
        const width: ViewerWidth = view.kind === 'video' ? 'wide' : view.kind === 'article' ? 'reading' : 'fit'
        return { status: 'ok', source, title: post.title, page_path: post_page_path(post), width, kind: view.kind, props: { post, view } }
    }

    if (source === 'guide') {
        const guide = getGuideBySlug(id)
        if (!guide) return { status: 'not_found', page_path: guidePath(id) }
        return { status: 'ok', source, title: guide.title, page_path: guidePath(guide.slug), width: 'reading', kind: 'guide', props: { slug: guide.slug } }
    }

    if (source === 'warzone') {
        const issue = warzone.get_issue(id)
        if (!issue) return { status: 'not_found', page_path: '/warzone/' }
        const title = t(t_key('warzone.', underscored(issue.slug), '.page_title'))
        return { status: 'ok', source, title, page_path: issue.permalink_path, width: 'wide', kind: 'report', props: { issue } }
    }

    if (source === 'market') {
        const issue = market.get_issue(id)
        if (!issue) return { status: 'not_found', page_path: market.LATEST_PATH }
        const title = t(t_key('amamake_market.', underscored(issue.slug), '.page_title'))
        return { status: 'ok', source, title, page_path: issue.permalink_path, width: 'wide', kind: 'report', props: { issue } }
    }

    if (source === 'newsletter') {
        const issue = newsletter.get_issue(id)
        if (!issue) return { status: 'not_found', page_path: '/newsletter/' }
        const title = t(t_key('newsletter.', underscored(issue.slug), '.page_title'))
        return { status: 'ok', source, title, page_path: issue.permalink_path, width: 'wide', kind: 'report', props: { issue } }
    }

    if (source === 'values') {
        return { status: 'ok', source, title: values_page.frontmatter.title, page_path: '/alliance/values/', width: 'reading', kind: 'page', props: {} }
    }

    if (source === 'story') {
        const chapter = getChronicleChapterById(id)
        if (!chapter) return { status: 'not_found', page_path: '/alliance/story/' }
        const title = `${story_page.frontmatter.title} · Chapter ${chapter.number}: ${chapter.title}`
        return { status: 'ok', source, title, page_path: `/alliance/story/${chapter.id}/`, width: 'wide', kind: 'page', props: { chapter_id: chapter.id } }
    }

    return { status: 'not_found', page_path: '/' }
}

/** A source name from a query string, or null. */
export function parse_viewer_source(value: string | null): ViewerSource | null {
    return VIEWER_SOURCES.includes(value as ViewerSource) ? value as ViewerSource : null
}
