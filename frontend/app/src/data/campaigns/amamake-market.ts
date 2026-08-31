/** Amamake Market Report · public monthly issue. First edition August YC128. */

export const COVER_IMAGE = '/images/home-amamake-cover.jpg'

export const SLUG = 'amamake-market' as const
export const CANONICAL_PATH = `/campaigns/${SLUG}/` as const
export const ALLIANCE_PATH = `/alliance/campaigns/${SLUG}/` as const

export const YC_YEAR = 128
export const PUBLISHED_AT = new Date('2026-08-31T00:00:00Z')

/** Headline ISK on the content-hub card (inferred fills, not destroyed). */
export const ISK_SOLD = 1_224_512_972_344
