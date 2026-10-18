import type { BadgeSize, EvEImageServiceSize } from '@dtypes/layout_components'

export interface EntityBadgeSize {
    /** Logo width and height in px. */
    logo:       number;
    /** EVE image server size to request for the logo. */
    quality:    EvEImageServiceSize;
    /** Gap between the logo and the text. */
    gap:        string;
}

/** Sizes shared by the corporation and alliance badges. */
export const ENTITY_BADGE_SIZES: Record<BadgeSize, EntityBadgeSize> = {
    xs: { logo: 24, quality: 32, gap: 'var(--space-3xs)' },
    sm: { logo: 32, quality: 32, gap: 'var(--space-2xs)' },
    lg: { logo: 64, quality: 64, gap: 'var(--space-s)' },
}

export const entity_badge_size = (size?: BadgeSize): EntityBadgeSize =>
    ENTITY_BADGE_SIZES[size ?? 'sm'] ?? ENTITY_BADGE_SIZES.sm
