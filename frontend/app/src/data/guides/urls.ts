/** Maps wiki path (without /en prefix) to local guide slug. */
export const GUIDE_SLUG_BY_WIKI_PATH: Record<string, string> = {
    'alliance/Academy/Faction_Warfare_Plexing': 'faction-warfare-plexing',
    'alliance/Academy/new-player-fleet-guide': 'new-player-fleet-guide',
    'guides/Abyss': 'abyssals',
    'guides/Alesis-Overview-Guide': 'overview-guide',
    'alliance/Academy/faction-warfare-advantage': 'faction-warfare-advantage',
    'guides/pochven-standings': 'pochven-standings',
    'guides/zohar-hunting': 'zohar-hunting',
    'guides/rendezvous-wolf': 'rendezvous-wolf',
    'guides/level5s': 'level5-missions',
    'guides/Abyss/Electrical/Solo/Stormbringer': 'abyss-stormbringer-t6-electrical',
    'guides/Abyss/Dark/Duo/Jackdaw': 'abyss-duo-jackdaws-t6-dark',
    'guides/Abyss/Firestorm/Trio/Nergal': 'abyss-nergal-trio-t6-firestorm',
    'guides/Abyss/Dark/Trio/Hawk': 'abyss-trio-hawk-t5-dark',
}

export const GUIDES_INDEX_PATH = '/guides/'

export function guidePath(slug: string): string {
    return `/guides/${slug}/`
}

export function guideUrl(slug: string): string {
    return `https://my.minmatar.org/guides/${slug}/`
}
