import type { GuideMeta } from '@/data/guides/types'

export const GUIDES_INDEX_COVER = {
    image: '/images/metaguide-wide.jpg',
    image_990: '/images/metaguide-wide.jpg',
}

const CATEGORY_COVERS: Record<GuideMeta['category'], string> = {
    'Faction Warfare': '/images/guides/wiki_frontlines.png',
    'PVP': '/images/fleets-cover.jpg',
    'PVE': '/images/fitting-cover.jpg',
    'Utility': '/images/intel-cover.jpg',
}

const GUIDE_COVERS: Record<string, string> = {
    'faction-warfare-advantage': '/images/guides/wiki_frontlines.png',
    'faction-warfare-plexing': '/images/guides/wiki_frontlines.png',
    'rendezvous-wolf': '/images/combatlog-tile-background.jpg',
    'new-player-fleet-guide': '/images/fleets-cover.jpg',
    'abyssals': '/images/fitting-cover-wormhole.jpg',
    'abyss-stormbringer-t6-electrical': '/images/fitting-cover.jpg',
    'abyss-duo-jackdaws-t6-dark': '/images/blackops-cover.jpg',
    'abyss-nergal-trio-t6-firestorm': '/images/blackops-cover.jpg',
    'abyss-trio-hawk-t5-dark': '/images/fitting-cover.jpg',
    'level5-missions': '/images/guides/guides/level5s/cleansing_fire.jpg',
    'pochven-standings': '/images/guides/pochven-map.png',
    'zohar-hunting': '/images/guides/guides/level5s/wrath_of_angels.png',
    'bookmarks': '/images/intel-cover.jpg',
    'overview-guide': '/images/guides/guides/overview_guide/alesis1.jpg',
}

export function getGuideCoverImage(guide: Pick<GuideMeta, 'slug' | 'category'>): string {
    return GUIDE_COVERS[guide.slug] ?? CATEGORY_COVERS[guide.category] ?? '/images/alliance-cover.jpg'
}
