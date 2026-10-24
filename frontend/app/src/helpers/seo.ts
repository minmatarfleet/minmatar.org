import sitemap from '@json/sitemap.json'
import { ui, defaultLang } from '@i18n/ui'
import { get_prod_url, is_prod_mode } from '@helpers/env'

type TranslationKey = keyof typeof ui.en
type Translate = (key: TranslationKey) => string

type SitemapPage = {
    slug: string
    path: string
    description?: string
}

export interface PageSeo {
    title: string
    description: string
}

const FLEET_DETAIL_PATH = /^\/fleets\/(upcoming|history)\/(\d+)\/$/

export function get_site_origin(fallbackOrigin?: string): string {
    if (is_prod_mode()) {
        return get_prod_url().replace(/\/$/, '')
    }
    return (fallbackOrigin ?? get_prod_url()).replace(/\/$/, '')
}

export const NOINDEX_PATH_PREFIXES = ['/partials/', '/redirects/', '/go/'] as const

export function is_noindex_path(pathname: string): boolean {
    return NOINDEX_PATH_PREFIXES.some((prefix) => pathname.startsWith(prefix))
}

function has_translation(key: string): key is TranslationKey {
    return Object.prototype.hasOwnProperty.call(ui[defaultLang], key)
}

export function normalize_pathname(pathname: string): string {
    const path = pathname.split('?')[0].split('#')[0]
    if (path === '' || path === '/') return '/'
    const with_leading_slash = path.startsWith('/') ? path : `/${path}`
    return with_leading_slash.endsWith('/') ? with_leading_slash : `${with_leading_slash}/`
}

export function pathname_from_return_target(value: string, base: string): string | null {
    try {
        const url = new URL(value, base)
        const base_url = new URL(base)
        if (url.origin !== base_url.origin) return null
        return normalize_pathname(url.pathname)
    } catch {
        return null
    }
}

export function is_auth_init_redirect(location: string, base: string): boolean {
    try {
        const target = new URL(location, base)
        return normalize_pathname(target.pathname) === '/redirects/auth_init/'
    } catch {
        return false
    }
}

function description_for_slug(
    slug: string,
    t: Translate,
    sitemap_description?: string,
): string {
    const meta_key = `page_finder.${slug}.meta_description`
    if (has_translation(meta_key)) return t(meta_key)
    if (sitemap_description && has_translation(sitemap_description)) return t(sitemap_description)
    return t('generic.meta_description')
}

function match_sitemap_page(pathname: string): SitemapPage | null {
    const pages = sitemap as SitemapPage[]
    const exact = pages.find((page) => normalize_pathname(page.path) === pathname)
    if (exact) return exact

    const prefixes = pages
        .map((page) => ({ page, path: normalize_pathname(page.path) }))
        .filter(({ path }) => path !== '/' && pathname.startsWith(path))
        .sort((a, b) => b.path.length - a.path.length)

    return prefixes[0]?.page ?? null
}

export function page_seo_for_path(pathname: string, t: Translate): PageSeo | null {
    const path = normalize_pathname(pathname)
    const fleet_detail = path.match(FLEET_DETAIL_PATH)
    if (fleet_detail) {
        const parent_slug = fleet_detail[1] === 'upcoming' ? 'fleets.upcoming' : 'fleets.history'
        const parent = (sitemap as SitemapPage[]).find((page) => page.slug === parent_slug)
        return {
            title: `${t('fleet')} ${fleet_detail[2]}`,
            description: description_for_slug(parent_slug, t, parent?.description),
        }
    }

    const match = match_sitemap_page(path)
    if (!match) return null

    const title_key = `${match.slug}.page_title`
    if (!has_translation(title_key)) return null

    return {
        title: t(title_key),
        description: description_for_slug(match.slug, t, match.description),
    }
}
