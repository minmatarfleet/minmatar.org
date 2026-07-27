import { getGuideBySlug } from '@/data/guides'
import { getGuideCoverImage, getGuideSeoImage } from '@/data/guides/covers'
import type { GuideMeta } from '@/data/guides/types'

const LEARNING_COVER_FALLBACKS: Record<string, string> = {
    'alliance-values': '/images/corporations-tile-background.webp',
    'alliance-playstyle': '/images/fleets-cover.jpg',
}

const DEFAULT_LEARNING_COVER = '/images/guides-cover.jpg'

/** Prefer guide SEO/share card, then guide cover, then learning-specific fallbacks. */
export function getLearningCoverImage(slug: string): string {
    const guide = getGuideBySlug(slug)
    if (guide) {
        return getGuideSeoImage(guide)
    }

    if (LEARNING_COVER_FALLBACKS[slug]) {
        return LEARNING_COVER_FALLBACKS[slug]
    }

    // Slugs present in the guide cover/SEO maps (e.g. navy guides) without a markdown module.
    const probe = { slug, category: 'Utility' as GuideMeta['category'] }
    const mapped = getGuideSeoImage(probe)
    const utilityFallback = getGuideCoverImage({ slug: '__missing__', category: 'Utility' })
    if (mapped !== utilityFallback) {
        return mapped
    }

    return DEFAULT_LEARNING_COVER
}
