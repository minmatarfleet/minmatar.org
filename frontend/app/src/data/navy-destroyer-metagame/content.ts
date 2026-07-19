import type { GlossaryEntry } from './types'

export const guideMeta = {
    title: 'Faction Warfare Destroyer Guide',
    edition: 'Web Edition',
    yc: 'YC 128',
    originalEdition: 'First Edition · YC 126',
    publisher: 'Minmatar Fleet Alliance Thinkspeak Editions',
    location: 'Sosala, The Bleak Lands',
    coverImage: '/images/doctrines-cover.jpg',
    coverAlt: 'EVE Online faction warfare destroyers fighting in a plex',
    firstEditionUrl: 'https://drive.google.com/file/d/1Vr3T2Z0pPlDkj8sqsS0EBhDcUbLnol2p/view',
    firstEditionRedditUrl: 'https://www.reddit.com/r/Eve/comments/1c7x1ps/the_navy_destroyer_metagame_guide_2024_edition/',
}

export const credits = {
    firstEditionAuthor: 'Furl0w',
    firstEditionLabel: 'First Edition · YC 126',
    thanks:
        'Special thanks from the First Edition to Jakub Tivianne, Thehin Zamayid, the FL33T and BSB discords, and Faye Vaelent for design and editing.',
    quotes: [
        { text: 'This is badass', attribution: 'Casper24' },
        { text: "It's a great guide, good work", attribution: 'Dato Koppla' },
    ],
}

export type GuideResource = {
    title: string
    href: string
    note: string
}

export const additionalResources: GuideResource[] = [
    {
        title: 'Navy Destroyer Metagame — First Edition (Furl0w, YC 126)',
        href: guideMeta.firstEditionUrl,
        note: 'Original PDF this web edition grows from—fits, matchup notes, and solo plex tactics for navy destroyers.',
    },
    {
        title: 'First Edition Reddit announcement',
        href: guideMeta.firstEditionRedditUrl,
        note: 'Furl0w’s 2024 announcement thread for the original guide.',
    },
    {
        title: 'EVE Faction Warfare Yearbook (T Sky / EVE Frigates)',
        href: 'https://patreon.com/EVEFrigates',
        note: 'Deeper yearly frigate and destroyer reference when you want more hulls and engagement data than this guide covers.',
    },
    {
        title: 'Faction Warfare Complexes (this site)',
        href: '/guides/faction-warfare-plexing/',
        note: 'Landing, gates, site sizes, and LP/VP tables for the plexes you are fighting in.',
    },
    {
        title: 'Faction Warfare Basics (this site)',
        href: '/guides/faction-warfare-basics/',
        note: 'Warzone map, system types, contested vs advantage.',
    },
    {
        title: 'Faction Warfare Frigate Guide (this site)',
        href: '/guides/navy-frigate-guide/',
        note: 'When Scout plexes still matter—navy and T1 frigates, archetypes, and 1v1 charts.',
    },
]

export const introduction = [
    'After the <a href="https://www.eveonline.com/news/view/uprising-expansion-now-live">Uprising</a> expansion, the faction warfare meta shifted entirely to destroyers. Scout complexes became largely unimportant, and a destroyer could run nearly every complex, making them the warzone\'s best ISK printer. Navy destroyers raised the stakes even further: more EHP, better projection, and more damage than T1 hulls. They could even take on cruisers.',
    'Two years later, navy hulls are still the default tool for faction warfare pilots, and the most common destroyers on directional scanners when you are undocked. T1 destroyers remain everywhere as farm boats and cheap practice hulls—Algos, Thrasher, Coercer, and Dragoon especially.',
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
    'The guide is primarily written for solo pilots. Many of these fits are wrong for structured gang work; there are better options when you are flying with others. The example fittings are not meant to be the final word. Module tier, rig choice, and bling all matter, but each one is a solid representation of its archetype and will perform as described. Common variants (refits) will be called out, as well.',
    'Matchup notes describe the optimal line when nothing else is in play. If you know your opponent\'s fit, if you have fought the same pilot twice in a row, or if local conditions differ, change the plan. Being predictable is sometimes worse than being slightly suboptimal.',
]

export const metagameSummary = [
    {
        archetype: 'Brawl',
        text: 'Hug them and win the trade. Blaster Catalyst Navy Issue is the flexible favourite for slide-ins; Cormorant Navy Issue is the one-trick that stat-checks most destroyers once both ships are stuck at zero. Soft into kiters that never let you land. Coercer Navy Issue plate + neuts and Dragoon live here when the job is to turn their tank off and grind.',
    },
    {
        archetype: 'Overprop',
        text: '10MN lines that refuse classic MWD + scram + web opens. Catalyst Navy Issue 10mn is the gold standard; Algos practices the same fights cheap; Cormorant Navy Issue 10mn is a real overprop option with scram rails; Talwar Fleet Issue (Cradle of War) is the new thief stealing those lines while its solo meta is still forming.',
    },
    {
        archetype: 'Kite',
        text: 'Hold outside their apply — point-range DPS that punishes anyone who punches in. Coercer Navy Issue owns the band with beam or locus pulse: unmatched high-grounds damage, miserable as a pure hunter. Slow and two-mid locked, but the scariest destroyer to slide into cold.',
    },
    {
        archetype: 'Opportunist',
        text: 'Commit only when the kill is free, abort when it is not. Thrasher Fleet Issue is the fan favourite despite soft 1v1 charts — speed, 280 mm alpha into SAAR frigates, and MWD bloom tricks. T1 Thrasher teaches the same artillery / autocannon choice before Fleet prices.',
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
    { id: 'introduction', title: 'Introduction' },
    { id: 'considerations', title: 'Considerations of the Metagame', shortTitle: 'Considerations' },
    { id: 'disclaimers', title: 'Disclaimers', shortTitle: 'Disclaimers' },
    { id: 'summary', title: 'Summary of the Metagame', shortTitle: 'Summary' },
    { id: 'matchups', title: 'Matchup Charts', shortTitle: 'Charts' },
    { id: 'catalyst', title: 'Catalyst Navy Issue' },
    { id: 'coercer', title: 'Coercer Navy Issue' },
    { id: 'thrasher', title: 'Thrasher Fleet Issue' },
    { id: 'cormorant', title: 'Cormorant Navy Issue' },
    { id: 'talwar', title: 'Talwar Fleet Issue' },
    { id: 'algos', title: 'Algos' },
    { id: 'thrasher-t1', title: 'Thrasher' },
    { id: 'coercer-t1', title: 'Coercer' },
    { id: 'dragoon', title: 'Dragoon' },
    { id: 'glossary', title: 'Glossary', shortTitle: 'Glossary' },
    { id: 'resources', title: 'Additional Resources', shortTitle: 'Resources' },
]
