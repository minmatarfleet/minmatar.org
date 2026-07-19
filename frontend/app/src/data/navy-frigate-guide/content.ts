import type { GlossaryEntry } from './types'

export const guideMeta = {
    title: 'Faction Warfare Frigate Guide',
    edition: 'Web Edition',
    yc: 'YC 128',
    originalEdition: 'First Edition · YC 128',
    publisher: 'Minmatar Fleet Alliance Thinkspeak Editions',
    location: 'Sosala, The Bleak Lands',
    coverImage: '/images/doctrines-cover.jpg',
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
    'The frigate metagame looks quite different from the destroyer metagame. Scram-kiting matters more: hull projection bonuses are weaker, so the range you hold decides most 1v1s. Instead of a binary high-ground chart, you get several viable archetypes at once—brawl under ~5 km, scram-kite at 7–10 km, web-kite around 10–13 km, and pure kite past ~16 km. Kiters with high ground beat brawlers at the wrong range; brawlers with high ground beat kiters who land on zero.',
    'Frigates also run several equally viable archetypes. With a frigate on d-scan, you often cannot tell whether it is kite, scram-kite, or brawl. You lean on local knowledge, scouting, and sometimes assuming the worst before you slide.',
    'One surprise if you only know destroyers: most solo frigate brawlers use an afterburner with scram, not a microwarpdrive. That keeps prop active under scram. MWD + disruptor lines still exist—especially on Slicers and some Hookbills—but they are a different ship story from the AB + scram default.',
]

export const considerationBullets = [
    'Scram-kiting is the center of the meta. Most navy fights resolve at the edge of scram, not at zero.',
    'Ammo choice matters more than on destroyers. Matchups are often close; the wrong crystal or rocket type flips them.',
    'T1 frigates still appear constantly and still teach the same archetypes, but navy hulls out-control and out-tank them in fair trades.',
    'Anti-kite fits are real here. Dual-prop or MWD answers that barely matter in destroyer charts show up often in Scout plexes.',
]

export const disclaimers = [
    'The guide is primarily written for solo pilots. Many of these fits are wrong for structured gang work; there are better options when you are flying with others. The example fittings are not meant to be the final word. Module tier, rig choice, and bling all matter, but each one is a solid representation of its archetype and will perform as described. Common variants (refits) will be called out, as well.',
    'Matchup notes describe the optimal line when nothing else is in play. If you know your opponent\'s fit, if you have fought the same pilot twice in a row, or if local conditions differ, change the plan. Being predictable is sometimes worse than being slightly suboptimal.',
]

export const metagameSummary = [
    {
        ship: 'Caldari Navy Hookbill',
        text: 'Dominant if you\'re looking for a control fit. Generous number of mid slots allows for multiple webs, or even cheeky EWAR fittings to punch up.',
    },
    {
        ship: 'Federation Navy Comet',
        text: 'Generalist. Wins raw DPS trades against most frigates, but can be controlled by double webs. Start here if you want something that you can use across a wide variety of situations.',
    },
    {
        ship: 'Imperial Navy Slicer',
        text: 'Perfect at kiting. Cheap enough to learn without every loss hurting. Teaches kiting, manual piloting, capacitor management, and every skill you\'ll need for interceptors and nanogang.',
    },
    {
        ship: 'Republic Fleet Firetail',
        text: 'Home team… we have to fly it every now and then. Speed plus double web makes it a bit more opportunistic, but it\'s generally not the best hull.',
    },
    {
        ship: 'Vigil Fleet Issue',
        text: 'Long webs and rockets. Web-kite with Javelin when you want range; scram-kite with Rage when you want a mid-range missile line.',
    },
    {
        ship: 'Rifter',
        text: 'Practically plays the same as the Firetail in many lineups—learn the lessons for the Firetail before you pay higher prices.',
    },
    {
        ship: 'Tristan',
        text: 'Less critical these days, where it was the ideal ship for generating income in faction warfare. Still common, though.',
    },
    {
        ship: 'Breacher',
        text: 'BearThatCares\'s favorite frigate. Great for punishing pilots, and even better if you have a small gang with you.',
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
    { id: 'rifter', title: 'Rifter' },
    { id: 'tristan', title: 'Tristan' },
    { id: 'breacher', title: 'Breacher' },
    { id: 'glossary', title: 'Glossary', shortTitle: 'Glossary' },
    { id: 'resources', title: 'Additional Resources', shortTitle: 'Resources' },
]
