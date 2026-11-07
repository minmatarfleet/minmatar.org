/** Shared bits of the Manage learning screen. */

/** Content kinds, in the order the Kind select lists them (backend ContentKind). */
export const GUIDE_KINDS = ['guide', 'blog', 'page', 'youtube', 'external', 'other'] as const

/** A guide-kind page lives here; its link is this plus the slug. */
export const GUIDE_PATH_PREFIX = '/learning/guides/'

/** A certificate's page. */
export const CERTIFICATE_PATH_PREFIX = '/learning/certificates/'

export const guide_url = (slug: string) => `${GUIDE_PATH_PREFIX}${slug}/`

/** Lowercase, dashes: what the backend's slugify keeps. */
export const slugify = (text: string): string =>
    text
        .toLowerCase()
        .normalize('NFKD')
        .replace(/[^\w\s-]/g, '')
        .trim()
        .replace(/[\s_-]+/g, '-')
        .replace(/^-+|-+$/g, '')
