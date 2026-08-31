/** Shared cover images for tribe groups (by group id). */

export const TRIBE_GROUP_COVERS: Record<number, string> = {
    1: '/images/dreads-cover.webp',
    2: '/images/carriers-cover.webp',
    3: '/images/faxes-cover.webp',
    12: '/images/technology-cover.webp',
    15: '/images/advocate-cover.webp',
    13: '/images/thinkspeak-cover.webp',
    14: '/images/readiness-cover.webp',
    5: '/images/capital-production-cover.webp',
    7: '/images/planetary-interaction-cover.webp',
    6: '/images/mining-cover.webp',
    4: '/images/subcapital-production-cover.webp',
    11: '/images/sellorders-tile-background.webp',
    10: '/images/contracts-tile-background.webp',
    9: '/images/freight-tile-background.webp',
    17: '/images/tournament-cover.webp',
    16: '/images/loyalty-points-cover.webp',
    18: '/images/fcs-cover.webp',
}

export const TRIBE_COVERS: Record<number, string> = {
    1: '/images/capitals-tribe-cover.webp',
    4: '/images/comunity-tribe-cover.webp',
    2: '/images/industry-tribe-cover.webp',
    3: '/images/market-tribe-cover.webp',
}

export const TRIBES_COVER_FALLBACK = '/images/tribes-fallback-cover.webp'

export function tribe_group_cover(group_id: number): string {
    return TRIBE_GROUP_COVERS[group_id] ?? TRIBES_COVER_FALLBACK
}

export function tribe_cover(tribe_id: number): string {
    return TRIBE_COVERS[tribe_id] ?? TRIBES_COVER_FALLBACK
}
