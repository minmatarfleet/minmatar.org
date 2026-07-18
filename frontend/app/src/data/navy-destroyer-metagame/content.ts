import type { GlossaryEntry } from './types'

export const guideMeta = {
    title: 'The Navy Destroyer Metagame',
    edition: 'Web Edition',
    yc: 'YC 128',
    originalEdition: 'First Edition · YC 126',
    publisher: 'Minmatar Fleet Alliance Thinkspeak Editions',
    location: 'Sosala, The Bleak Lands',
    coverImage: '/images/doctrines-cover.jpg',
    coverAlt: 'Fleet destroyers engaged in faction warfare',
    firstEditionUrl: 'https://drive.google.com/file/d/1Vr3T2Z0pPlDkj8sqsS0EBhDcUbLnol2p/view',
    firstEditionRedditUrl: 'https://www.reddit.com/r/Eve/comments/1c7x1ps/the_navy_destroyer_metagame_guide_2024_edition/',
}

export const credits = {
    firstEditionAuthor: 'Furl0w',
    firstEditionLabel: 'First Edition · YC 126',
    thanks:
        'The original First Edition owed special thanks to Jakub Tivianne for insightful feedback and discussion, Thehin Zamayid for his comments, the FL33T and BSB discords, and everyone who motivated Furl0w to finish the guide. Faye Vaelent designed and edited that print edition.',
    quotes: [
        { text: 'This is badass', attribution: 'Casper24' },
        { text: "It's a great guide, good work", attribution: 'Dato Koppla' },
    ],
}

export const guideHistory = [
    {
        id: 'first-edition',
        dateLabel: '2024',
        yc: 'YC 126',
        title: 'First Edition',
        description:
            'Furl0w publishes the original guide: fits, matchup notes, and solo plex tactics for faction warfare navy destroyers.',
        link: {
            href: guideMeta.firstEditionUrl,
            label: 'Read PDF',
        },
    },
    {
        id: 'web-edition',
        dateLabel: 'June 21, 2026',
        yc: 'YC 128',
        title: 'Web Edition',
        description:
            'Adapted for my.minmatar.org with searchable fits, matchup charts, and live [NVY] fittings in the Fleet library.',
    },
] as const satisfies readonly import('./types').GuideHistoryEntry[]

export const introduction = [
    'After the <a href="https://www.eveonline.com/news/view/uprising-expansion-now-live">Uprising</a> expansion, the faction warfare meta shifted entirely to destroyers. Scout complexes became largely unimportant, and a destroyer could run nearly every complex, making them the warzone\'s best ISK printer. Navy destroyers raised the stakes even further: more EHP, better projection, and more damage than T1 hulls. They could even take on cruisers.',
    'Two years later, they are still the default tool for faction warfare pilots, and the most common ship on directional scanners when you are undocked.',
    'What follows is a living guide that covers the archetypes you\'ll actually see in space, and all of their matchups. It includes details on the complex high ground, practical notes on when to commit, when to bail, and where a fit can be adjusted.',
]

export const considerations = [
    'The destroyer metagame looks quite different from the frigate metagame. Scram-kiting matters less: most destroyers, even blaster hulls, can scram-kite when they want to, thanks to the hull\'s built-in projection bonus. What you get instead is closer to a binary chart: kiters with high ground beat brawlers, and brawlers with high ground beat kiters.',
    'Destroyers also run several equally viable archetypes. With a destroyer on d-scan, you often cannot tell whether it\'s kite or brawl. You lean on local knowledge, scouting, and sometimes assuming the worst before you slide.',
    'One surprise for frigate pilots: most brawling fits use microwarpdrives, not an afterburner. That trades some range control against other AB brawlers for advantages that tend to win out:',
]

export const considerationBullets = [
    'AB destroyers are slow, and destroyer lock speed is slower than frigate lock speed. A microwarpdrive helps you catch kiters sliding into a plex.',
    'The speed lets you reposition inside a plex when someone appears on d-scan while you are killing the NPC 10 km off the beacon.',
    'Overpropped 10MN destroyers are real. Against a 10MN + point fit, running a microwarpdrive keeps you in the range-control fight.',
    'Faction warfare is group-heavy, and group play expects a microwarpdrive. You do not want to be 60 km behind the fight.',
    'The more brawlers fit a microwarpdrive, the less you are punished for fitting one yourself. That becomes a self-reinforcing loop.',
]

export const disclaimers = [
    'This guide is written for soloing. Many of these fits are wrong for structured gang work; there are better options when you are flying with others. The example fits are not meant to be the final word. Module tier, rig choice, and bling all matter, but each one is a solid representation of its archetype and will perform as described.',
    'Matchup notes describe the optimal line when nothing else is in play. If you know your opponent’s fit, if you have fought the same pilot twice in a row, or if local conditions differ, change the plan. Being predictable is sometimes worse than being slightly suboptimal.',
    'The Talwar Fleet Issue section covers a ship released after the First Edition. Its matchups are community early reads; entries marked ? are still being tested as the meta settles.',
]

export const metagameSummary = [
    {
        ship: 'Catalyst Navy Issue',
        text: 'The most flexible and widely favoured destroyer in both warzones. Its two main lines (blaster brawl and 10MN rail) cover each other’s weaknesses: you do not want to be on top of the blaster fit, but you do want to hug the kiter, so even with high ground the defender faces awkward choices. Probably the best slide-in hull in the class.',
    },
    {
        ship: 'Coercer Navy Issue',
        text: 'The scariest destroyer to punch into. Kiting variants (beam or locus pulse) deliver unmatched point-range DPS; brawling variants bring enormous EHP and frightening neuts. Slow speed and only two mid slots make it a miserable hunter, but a brutal ambush ship.',
    },
    {
        ship: 'Thrasher Fleet Issue',
        text: 'Weak on paper in many 1v1 charts, still a fan favourite. Speed lets clever pilots disengage losing fights and commit only when the kill is there. Strong punching down (280 mm alpha deleting SAAR frigates) and up (MWD sig-bloom reduction for manual piloting).',
    },
    {
        ship: 'Cormorant Navy Issue',
        text: 'A one-trick pony (slow, awkward active-tank bonus) that stat-checks most other destroyers at brawl range. Alternative fits exist but usually need more bling to justify the hull over a Catalyst.',
    },
    {
        ship: 'Talwar Fleet Issue',
        text: 'The newest navy destroyer (Cradle of War, YC 128). Early solo play centres on a 10MN rocket brawler that beats many classic MWD + scram + web lines; fleet light-missile fits look weak so far. Meta is still forming.',
    },
]

export const glossary: GlossaryEntry[] = [
    { term: 'Brawling', definition: 'Fighting up close within damage range of the enemy.' },
    { term: 'High grounds', definition: 'The pilot already inside the plex. Most fights start with a slide-in; the inside pilot sets the opening range.' },
    { term: 'Kiting', definition: 'Staying outside the enemy’s effective range while still applying damage.' },
    { term: 'Low grounds', definition: 'The pilot outside the plex. You can scout and choose when to initiate, but you start at a range disadvantage.' },
    { term: 'MSB', definition: 'Medium Shield Booster' },
    { term: 'MASB', definition: 'Medium Ancillary Shield Booster' },
    { term: 'Neuts', definition: 'Energy neutralizers' },
    { term: 'Plex', definition: 'Faction warfare complex: a gated (or, for Open, ungated) deadspace site where most FW fights happen.' },
    { term: 'SAAR', definition: 'Small Ancillary Armor Repairer' },
    { term: 'Scram-kiting', definition: 'Kiting at the edge of scrambler range (roughly 8-9 km).' },
    { term: 'Web-kiting', definition: 'Kiting at the edge of webifier range (roughly 10-15 km depending on hull and web).' },
]

export const guideSections = [
    { id: 'credits', title: 'Credits', shortTitle: 'Credits' },
    { id: 'history', title: 'History', shortTitle: 'History' },
    { id: 'introduction', title: 'Introduction' },
    { id: 'considerations', title: 'Considerations of the Metagame', shortTitle: 'Considerations' },
    { id: 'disclaimers', title: 'Disclaimers & Summary', shortTitle: 'Summary' },
    { id: 'matchups', title: 'Matchup Charts', shortTitle: 'Charts' },
    { id: 'catalyst', title: 'Catalyst Navy Issue' },
    { id: 'coercer', title: 'Coercer Navy Issue' },
    { id: 'thrasher', title: 'Thrasher Fleet Issue' },
    { id: 'cormorant', title: 'Cormorant Navy Issue' },
    { id: 'talwar', title: 'Talwar Fleet Issue' },
    { id: 'glossary', title: 'Glossary', shortTitle: 'Glossary' },
]
