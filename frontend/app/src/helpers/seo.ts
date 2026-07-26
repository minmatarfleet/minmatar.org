import { get_prod_url, is_prod_mode } from '@helpers/env'

export function get_site_origin(fallbackOrigin?: string): string {
    if (is_prod_mode()) {
        return get_prod_url().replace(/\/$/, '')
    }
    return (fallbackOrigin ?? get_prod_url()).replace(/\/$/, '')
}

export function build_canonical_url(
    path: string,
    translatePath: (path: string) => string,
    fallbackOrigin?: string,
): string {
    return new URL(translatePath(path), get_site_origin(fallbackOrigin)).href
}

export const NOINDEX_PATH_PREFIXES = ['/partials/', '/redirects/'] as const

export function is_noindex_path(pathname: string): boolean {
    return NOINDEX_PATH_PREFIXES.some((prefix) => pathname.startsWith(prefix))
}
