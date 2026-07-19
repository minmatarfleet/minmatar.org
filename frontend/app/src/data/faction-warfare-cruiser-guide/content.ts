import type { GlossaryEntry } from './types'

export const guideMeta = {
    title: 'Faction Warfare Cruiser Guide',
    edition: 'Web Edition',
    yc: 'YC 128',
    publisher: 'Minmatar Fleet Alliance Thinkspeak Editions',
    location: 'Sosala, The Bleak Lands',
    coverImage: '/images/warzone-cover.jpg',
    coverAlt: 'Cruisers engaged in faction warfare',
}

export const credits = {
    author: 'Dato Koppla',
}

export type GuideResource = {
    title: string
    href: string
    note: string
}

export const additionalResources: GuideResource[] = [
    {
        title: 'Faction Warfare Frigate Guide (this site)',
        href: '/guides/navy-frigate-guide/',
        note: 'Scout plexes and navy/T1 frigates—start here before stepping up to destroyers and cruisers.',
    },
    {
        title: 'Faction Warfare Destroyer Guide (this site)',
        href: '/guides/navy-destroyer-metagame/',
        note: 'Navy and T1 destroyers, archetypes, and 1v1 charts—the usual rung below cruiser plex work.',
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
        title: 'EVE Faction Warfare Yearbook (T Sky / EVE Frigates)',
        href: 'https://patreon.com/EVEFrigates',
        note: 'Deeper yearly hull reference when you want more engagement data than this guide covers.',
    },
]

export const introduction = [
    'With the release of moderate sites in the Cradle of War expansion and various ISK printing sites in Havoc, cruisers have become a staple of the faction warfare warzone. They decide who keeps the large complexes, who controls the advantage when fighting off small gangs, and are one of the better platforms for player versus player combat.',
    'This guide covers the hulls that you\'ll often see in the warzone, as well as the common archetypes that they fall into. We highly recommend that players start with destroyers before moving onto cruisers and frigates — see the <a href="/guides/navy-frigate-guide/">Frigate Guide</a> and <a href="/guides/navy-destroyer-metagame/">Destroyer Guide</a>.',
    'The vast majority of the knowledge from this guide comes from Dato Koppla, who was kind enough to open up his Pyfa for us!',
]

export const considerations = [
    'Cruiser fights are much slower and intentional than destroyer and frigate engagements. Mutual scram and web often commit both pilots: if you slingshot wrong at zero, you will not get those fifty meters back before the DPS race is decided. Since fitting is generally a bit more freeform, this leads to interesting decisions like neutron blasters versus ion blasters.',
    'Whereas frigates are much more of a rock-paper-scissors and destroyers are like a brawl in a pub, cruisers are much more like a dance. Many kite fits can still lose if a competent brawler punches in, and kiters cannot hold long point until the fight is over. The Exequror Navy Issue and Vexor Navy Issue punish greedy point holders.',
    'Utility highs matter significantly, much more than they do on frigate and destroyers. The capacitor race can often determine a solo fight, especially if you can turn off their tank or guns. Osprey Navy Issue is a great example of a platform that can abuse this.',
]

export const considerationBullets = [
    'High ground still wins openings.',
    'Once both ships land scram and web, you\'re generally committed.',
    'Reactive armor collapses polarized DPS, and cruisers have enough EHP to take advantage. Diversify drones.',
    'Dual prop hulls are leave-insurance: take free trades, AB and leave when it\'s not looking good.',
]

export const disclaimers = [
    'The guide is written for solo and small-gang pilots stocking contracts or holding plexes. Many of these fits are wrong for large structured fleets. Example fittings are solid representations of each archetype, not the final word — module tier, rig choice, and bling all matter. Check skills and ISK before undocking.',
    'Matchup charts and per-ship cards rate the example fits in this guide against each other (high ground vs low ground when nothing else is in local). Change the plan when you know the fit, the pilot, or the gang. Being predictable is sometimes worse than being slightly suboptimal.',
]

export const metagameSummary = [
    {
        archetype: 'Brawl',
        text: 'Win at scrambler range. Exequror Navy Issue is the apex gunboat; polarized Augoror Navy Issue can catch a lot of people off guard. HAMs are a fairly idiot-proof meat-grinder.',
    },
    {
        archetype: 'Kite',
        text: 'Hold outside of the range they can apply DPS at. Omen Navy Issue, laser boats, and rail boats are generally staples.',
    },
    {
        archetype: 'Active Control',
        text: 'Cap them out or out-rep them while you hold them down. Vexor Navy Issue is disgusting for this, and the Osprey Navy Issue can land some cheeky wins with dual neutralizers.',
    },
    {
        archetype: 'Dual-Prop',
        text: 'Take free trades, AB out or flash-tank the beacon when local is wrong. Scythe Fleet Issue and Stabber Fleet Issue are often seen doing this.',
    },
]

export const glossary: GlossaryEntry[] = [
    { term: 'Brawling', definition: 'Fighting up close within damage range of the enemy.' },
    { term: 'High grounds', definition: 'The pilot already inside the plex. Most fights start with a slide-in; the inside pilot sets the opening range.' },
    { term: 'Kiting', definition: 'Staying outside the enemy’s effective range while still applying damage.' },
    { term: 'Low grounds', definition: 'The pilot outside the plex. You can scout and choose when to initiate, but you start at a range disadvantage.' },
    { term: 'ENI', definition: 'Exequror Navy Issue' },
    { term: 'VNI', definition: 'Vexor Navy Issue' },
    { term: 'CNI', definition: 'Caracal Navy Issue' },
    { term: 'XLASB', definition: 'Extra Large Ancillary Shield Booster' },
    { term: 'RHML', definition: 'Rapid Heavy Missile Launcher' },
    { term: 'RLML', definition: 'Rapid Light Missile Launcher' },
    { term: 'Neuts', definition: 'Energy neutralizers' },
    { term: 'Plex', definition: 'Faction warfare complex: a gated (or, for Open, ungated) deadspace site where most FW fights happen.' },
    { term: 'TD', definition: 'Tracking Disruptor' },
]

const T1 = 'T1 Cruisers'
const NAVY = 'Navy Cruisers'
const CLOSING = 'Closing Notes'

export const guideSections = [
    { id: 'introduction', title: 'Introduction' },
    { id: 'considerations', title: 'Considerations of the Metagame', shortTitle: 'Considerations' },
    { id: 'disclaimers', title: 'Disclaimers', shortTitle: 'Disclaimers' },
    { id: 'summary', title: 'Summary of the Metagame', shortTitle: 'Summary' },
    { id: 'matchups', title: 'Matchup Charts', shortTitle: 'Charts' },
    // T1 first so Contents groups match page order
    { id: 'arbitrator', title: 'Arbitrator', group: T1 },
    { id: 'maller', title: 'Maller', group: T1 },
    { id: 'omen', title: 'Omen', group: T1 },
    { id: 'vexor', title: 'Vexor', group: T1 },
    { id: 'bellicose', title: 'Bellicose', group: T1 },
    { id: 'stabber', title: 'Stabber', group: T1 },
    { id: 'augni', title: 'Augoror Navy Issue', group: NAVY },
    { id: 'omenni', title: 'Omen Navy Issue', group: NAVY },
    { id: 'caracalni', title: 'Caracal Navy Issue', group: NAVY },
    { id: 'ospreyni', title: 'Osprey Navy Issue', group: NAVY },
    { id: 'eni', title: 'Exequror Navy Issue', group: NAVY },
    { id: 'vni', title: 'Vexor Navy Issue', group: NAVY },
    { id: 'scythefi', title: 'Scythe Fleet Issue', group: NAVY },
    { id: 'stabberfi', title: 'Stabber Fleet Issue', group: NAVY },
    { id: 'glossary', title: 'Glossary', shortTitle: 'Glossary', group: CLOSING },
    { id: 'resources', title: 'Additional Resources', shortTitle: 'Resources', group: CLOSING },
]
