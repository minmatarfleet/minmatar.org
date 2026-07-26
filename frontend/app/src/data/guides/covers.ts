import type { GuideMeta } from '@/data/guides/types'

export const GUIDES_INDEX_COVER = {
    image: '/images/guides-cover.jpg',
    image_990: '/images/guides-cover-990.jpg',
}

const CATEGORY_COVERS: Record<GuideMeta['category'], string> = {
    'Faction Warfare': '/images/guides/wiki_frontlines.png',
    'PVP': '/images/fleets-cover.jpg',
    'PVE': '/images/fitting-cover.jpg',
    'Utility': '/images/intel-cover.jpg',
}

const GUIDE_COVERS: Record<string, string> = {
    'faction-warfare-basics': '/images/guides/faction-warfare-basics-map.png',
    'faction-warfare-advantage': '/images/frontlines-cover.png',
    'faction-warfare-plexing': '/images/guides/wiki_frontlines.png',
    'navy-destroyer-metagame': '/images/doctrines-cover.jpg',
    'navy-frigate-guide': '/images/fits-cover.jpg',
    'faction-warfare-cruiser-guide': '/images/warzone-cover.jpg',
    'new-player-fleet-guide': '/images/fleets-cover.jpg',
    'abyssals': '/images/fitting-cover-wormhole.jpg',
    'abyss-stormbringer-t6-electrical': '/images/fitting-cover.jpg',
    'abyss-duo-jackdaws-t6-dark': '/images/blackops-cover.jpg',
    'abyss-nergal-trio-t6-firestorm': '/images/etherium-cover.jpg',
    'abyss-trio-hawk-t5-dark': '/images/combatlog-cover.jpg',
    'level5-missions': '/images/guides/guides/level5s/cleansing_fire.jpg',
    'pochven-standings': '/images/guides/pochven-map.png',
    'zohar-hunting': '/images/guides/guides/level5s/wrath_of_angels.png',
    'bookmarks': '/images/assets-cover.jpg',
}

/** Flat 1200×630 share cards for og:image / Twitter — not used as page heroes. */
const GUIDE_SEO_IMAGES: Record<string, string> = {
    'faction-warfare-basics': '/images/guides/seo/faction-warfare-basics.png',
    'faction-warfare-advantage': '/images/guides/seo/faction-warfare-advantage.png',
    'faction-warfare-plexing': '/images/guides/seo/faction-warfare-plexing.png',
    'navy-destroyer-metagame': '/images/guides/seo/navy-destroyer-metagame.png',
    'navy-frigate-guide': '/images/guides/seo/navy-frigate-guide.png',
    'faction-warfare-cruiser-guide': '/images/guides/seo/faction-warfare-cruiser-guide.png',
}

export function getGuideCoverImage(guide: Pick<GuideMeta, 'slug' | 'category'>): string {
    return GUIDE_COVERS[guide.slug] ?? CATEGORY_COVERS[guide.category] ?? '/images/alliance-cover.jpg'
}

export function getGuideSeoImage(guide: Pick<GuideMeta, 'slug' | 'category'>): string {
    return GUIDE_SEO_IMAGES[guide.slug] ?? getGuideCoverImage(guide)
}
