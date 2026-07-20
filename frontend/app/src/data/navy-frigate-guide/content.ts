import type { GlossaryEntry } from './types'

export const guideMeta = {
    title: 'Faction Warfare Frigate Guide',
    edition: 'Web Edition',
    yc: 'YC 128',
    originalEdition: 'First Edition · YC 128',
    publisher: 'Minmatar Fleet Alliance Thinkspeak Editions',
    location: 'Sosala, The Bleak Lands',
    coverImage: '/images/fits-cover.jpg',
    coverAlt: 'EVE Online faction warfare frigates in a Scout complex fight',
    firstEditionUrl: 'https://my.minmatar.org/guides/navy-frigate-guide/',
    firstEditionRedditUrl: 'https://patreon.com/EVEFrigates',
}

export type GuideResource = {
    title: string
    href: string
    note: string
}

export const additionalResources: GuideResource[] = [
    {
        title: 'EVE Faction Warfare Yearbook (T Sky / EVE Frigates)',
        href: 'https://patreon.com/EVEFrigates',
        note: 'Deeper per-ship and yearly meta reference if you want more detail than this guide covers.',
    },
    {
        title: 'Rixx Javix — 2025 Yearbook note & solo rankings (eveoganda)',
        href: 'https://eveoganda.blogspot.com/2025/11/2025-yearbook.html',
        note: 'Community write-up on the Yearbook and solo ship rankings.',
    },
    {
        title: 'Rixx Javix — Solo PvP Ships Ranked',
        href: 'https://eveoganda.blogspot.com/2025/02/solo-pvp-ships-ranked.html',
        note: 'Solo ship ranking commentary outside faction warfare navy frigates alone.',
    },
    {
        title: 'CrazyKinux — Brawl or kite (Hookbill lesson, 2026)',
        href: 'https://www.crazykinux.ca/2026/06/brawl-or-kite-how-veteran-pirate.html',
        note: 'Walkthrough of Hookbill rocket/scram versus light-missile/point fittings.',
    },
    {
        title: 'EVE University — Solo PvP',
        href: 'https://wiki.eveuniversity.org/Solo_PvP',
        note: 'General solo principles and FW complex combat as a starting arena.',
    },
    {
        title: 'EVE University — Faction warfare strategy and tactics',
        href: 'https://wiki.eveuniversity.org/Faction_warfare_strategy_and_tactics',
        note: 'Fitting basics, d-scan around plex gates, and staging. Some pages lag post-Uprising naming.',
    },
    {
        title: 'Brave Collective — Faction Warfare: A Guide (PDF)',
        href: 'https://static.adam4eve.eu/Guides/FactionWarfare/Faction%20Warfare_%20A%20Guide%20%5BBrave%20Collective%5D.pdf',
        note: 'Dated onboarding PDF; still useful for prop + tackle + web mid racks and flying cheap frigates often.',
    },
    {
        title: 'EVE Pro Guides — Federation Navy Comet fittings and tactics',
        href: 'http://eveproguides.com/faction-warfare-pvp-federation-navy-comet-fitting-tactics/',
        note: 'Older Comet write-up; treat fits as historical, keep the range-control ideas.',
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
        title: 'Faction Warfare Destroyer Guide (this site)',
        href: '/guides/navy-destroyer-metagame/',
        note: 'When you graduate Scouts into Smalls and start seeing navy destroyers on d-scan.',
    },
]

export const introduction = [
    'Scout complexes are less common for income these days, but still excellent for high-octane player-versus-player practice. Frigates are more intricate and fragile than destroyers and cruisers—minor mistakes kill you faster, which is why they are ideal for practicing core mechanics.',
    'Navy hulls are fairly dominant, but T1 hulls still show up constantly.',
    'This guide is written for pilots who already know how a complex works and want a practical guide for frigate fittings. It is not as comprehensive as the <a href="https://patreon.com/EVEFrigates">Faction Warfare Yearbook</a>—if you end up diving extremely deep into the frigate world, you will want to earmark that guide as well.',
    'The fits below are examples of archetypes you will actually see. Module tier, bling, and adjustments are expected as you improve over time.',
]

export const considerations = [
    'The frigate metagame operates quite a bit different than the destroyer and cruiser metagame. Hull projection bonuses are weaker, so the range you hold often decides the engagement. Kiters with high ground beat brawlers at the wrong range; brawlers with high ground beat kiters who land on zero.',
    'One surprise if you only know destroyers: most frigate brawlers use an afterburner. Microwarpdrives are often seen with warp disruptors instead of scram fits.',
]

export const considerationBullets = [
    'Scram-kiting is the center of the meta. Most navy fights resolve at the edge of scram range.',
    'Ammo choice matters, and the margins are much thinner than destroyer engagements.',
    'T1 frigates appear constantly and teach the archetypes, but are often dominated by navy hulls.',
    'Anti-kite is a real thing with frigates, whereas destroyers it doesn\'t matter as much.',
]

export const disclaimers = [
    'The guide is primarily written for solo pilots. Many of these fits are wrong for structured gang work; there are better options when you are flying with others. The example fittings are not meant to be the final word. Module tier, rig choice, and bling all matter, but each one is a solid representation of its archetype and will perform as described. Common variants (refits) will be called out, as well.',
    'Matchup notes describe the optimal line when nothing else is in play. If you know your opponent\'s fit, if you have fought the same pilot twice in a row, or if local conditions differ, change the plan. Being predictable is sometimes worse than being slightly suboptimal.',
]

export const metagameSummary = [
    {
        archetype: 'Brawl',
        text: 'Win the DPS race at scram range. Ships like the Federation Navy Comet are ideal here — raw damage wins most straight trades. There are some cheeky options like the Tristan that will allow you to learn the archetype.',
    },
    {
        archetype: 'Control',
        text: 'Stack webs and other tools so that the other pilot doesn\'t get to play. Caldari Navy Hookbill dominates here, as it has the mid slots to run multiple webs or even some electronic warfare. Breacher is a great way to learn this archetype.',
    },
    {
        archetype: 'Kite',
        text: 'Hold outside of their apply range and grind away. The Imperial Navy Slicer is king here, and it\'s cheap enough to learn on. Manual piloting, capacitor management, and grid awareness are key here.',
    },
    {
        archetype: 'Opportunist',
        text: 'If you know what someone is flying, there are a few direct counters that you can simply run them down in. Things like Slicers easily get clapped by anti-kite ships.',
    },
]

export const glossary: GlossaryEntry[] = [
    { term: 'Brawling', definition: 'Fighting up close within damage range of the enemy.' },
    { term: 'High grounds', definition: 'The pilot already inside the plex. Most fights start with a slide-in; the inside pilot sets the opening range.' },
    { term: 'Kiting', definition: 'Staying outside the enemy’s effective range while still applying damage.' },
    { term: 'Low grounds', definition: 'The pilot outside the plex. You can scout and choose when to initiate, but you start at a range disadvantage.' },
    { term: 'MASB', definition: 'Medium Ancillary Shield Booster' },
    { term: 'MSE', definition: 'Medium Shield Extender' },
    { term: 'Neuts', definition: 'Energy neutralizers' },
    { term: 'Plex', definition: 'Faction warfare complex: a gated (or, for Open, ungated) deadspace site where most FW fights happen.' },
    { term: 'SAAR', definition: 'Small Ancillary Armor Repairer' },
    { term: 'Scram-kiting', definition: 'Kiting at the edge of scrambler range (roughly 7-10 km on frigates).' },
    { term: 'Web-kiting', definition: 'Kiting at the edge of webifier range (roughly 10-15 km depending on hull and web).' },
]

export const guideSections = [
    { id: 'introduction', title: 'Introduction' },
    { id: 'considerations', title: 'Considerations of the Metagame', shortTitle: 'Considerations' },
    { id: 'disclaimers', title: 'Disclaimers', shortTitle: 'Disclaimers' },
    { id: 'summary', title: 'Summary of the Metagame', shortTitle: 'Summary' },
    { id: 'matchups', title: 'Matchup Charts', shortTitle: 'Charts' },
    { id: 'hookbill', title: 'Caldari Navy Hookbill' },
    { id: 'comet', title: 'Federation Navy Comet' },
    { id: 'slicer', title: 'Imperial Navy Slicer' },
    { id: 'firetail', title: 'Republic Fleet Firetail' },
    { id: 'vigil', title: 'Vigil Fleet Issue' },
    { id: 'tristan', title: 'Tristan' },
    { id: 'breacher', title: 'Breacher' },
    { id: 'glossary', title: 'Glossary', shortTitle: 'Glossary' },
    { id: 'resources', title: 'Additional Resources', shortTitle: 'Resources' },
]
