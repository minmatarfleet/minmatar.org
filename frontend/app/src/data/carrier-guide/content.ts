import type { CapitalHull, GuideSection, MetaBlock, TierList } from '@/data/capital-guide'

export const guideMeta = {
    title: 'Carrier Guide',
    edition: 'Web Edition',
    yc: 'YC 128',
    publisher: 'Minmatar Fleet Alliance',
    coverImage: '/images/carriers-cover.webp',
    seoImage: '/images/carriers-cover.webp',
    coverAlt: 'Carriers suitcasing and fighting in capital warfare',
}

export const credits = {
    author: 'BearThatCares',
    authorId: 634915984,
}

export const overview = [
    'Carriers are extremely popular in the meta right now, primarily for their conduit capability. In combat, they are slightly less useful, but support fighters (especially the Dromi) are excellent for subcapital engagements.',
    'Main characters are encouraged to train carriers, and fleet commanders are recommended to train command carriers. Our reasons for this are simple:',
]

export const overviewReasons = [
    'The ability to bring 25–30 pilots per carrier is strong for locations where we don\'t have a titan in the midpoint',
    'The ability to suitcase 2,000,000 m³ is critical for deployments',
    'Fighters are consistently being improved, and we believe they will be a key part of the meta shift',
]

export const overviewFollowUp =
    'If this is your first guide, read <a href="/guides/capital-ship-basics/">Capital Ship Basics</a> first.'

export const metaBlocks: MetaBlock[] = [
    {
        type: 'quote',
        text: 'Why does everyone fly armor carriers, Mr.ThatCares?',
    },
    {
        type: 'paragraph',
        html: 'This one is a bit more complicated, because shield carriers actually do more damage than armor carriers, and make the tradeoff on fighter speed and application. Ultimately, the reasoning is the same — energy neutralizers.',
    },
    {
        type: 'paragraph',
        html: 'Armor dreadnoughts are often neutralizing their primary target, and shield carriers lose 50% of their EHP once they\'re dry. After that, they\'re instantly deleted.',
    },
]

export const shipsLead =
    'Train and buy Archon. Thanatos is the armor alternate. Shield carriers fill tribe asset lists and niches — less common on FL33T grids. Tap a hull for Capitals fittings when we have them.'

export const fightersTable = {
    id: 'fighters',
    title: 'Fighters',
    headers: ['Type', 'Examples', 'Purpose'],
    rows: [
        ['Space superiority fighters', 'Equite, Locust, Satyr, Gram', 'Kill enemy fighters and drones'],
        ['Fighters', 'Templar, Dragonfly, Firbolg, Einherji', 'Primary damage against ships'],
        ['Support fighters', 'Cenobite, Scarab, Siren, Dromi', 'Tackle and EWAR for subcapital engagements'],
    ],
} as const

export const carrierHulls: Record<string, CapitalHull> = {
    archon: { id: 'archon', name: 'Archon', shortName: 'Archon', shipId: 23757 },
    thanatos: { id: 'thanatos', name: 'Thanatos', shortName: 'Thanatos', shipId: 23911 },
    nidhoggur: { id: 'nidhoggur', name: 'Nidhoggur', shortName: 'Nidhoggur', shipId: 24483 },
    chimera: { id: 'chimera', name: 'Chimera', shortName: 'Chimera', shipId: 23915 },
}

export const carrierTiers: TierList = {
    id: 'carrier-tiers',
    title: 'Carriers',
    lead: 'Armor doctrine leads. One suitcase Archon is better than zero.',
    rows: [
        { tier: 'S', hullIds: ['archon'] },
        { tier: 'C', hullIds: ['thanatos', 'nidhoggur'] },
        { tier: 'LC', hullIds: ['chimera'] },
    ],
}

export const guideSections: GuideSection[] = [
    { id: 'overview', title: 'Overview' },
    { id: 'meta', title: 'Meta' },
    { id: 'ships', title: 'Ships' },
    { id: 'fighters', title: 'Fighters' },
    { id: 'tribe', title: 'Tribe' },
]
