import type { CapitalHull, CrosstrainingRow, GuideSection, MetaBlock, TierList } from '@/data/capital-guide'

export const guideMeta = {
    title: 'Dread Guide',
    edition: 'Web Edition',
    yc: 'YC 128',
    publisher: 'Minmatar Fleet Alliance',
    coverImage: '/images/dreads-cover.webp',
    seoImage: '/images/dreads-cover.webp',
    coverAlt: 'Dreadnoughts on grid in capital warfare',
}

export const credits = {
    author: 'BearThatCares',
    authorId: 634915984,
}

export const overview = [
    'Dreadnoughts are our damage dealers. In Minmatar Fleet, they usually enter fights as part of an <strong>escalation chain</strong>, which means we usually have to start a fight before they can come in.',
    'For that reason, dreads are primarily flown on <strong>alts</strong>. Without a subcapital fleet, there is no fight. If there is no fight, there are no dreads.',
    'Before you start here, make sure you read the <a href="/learning/guides/capital-ship-basics/">Capital Ship Basics</a> guide.',
]

export const metaBlocks: MetaBlock[] = [
    {
        type: 'paragraph',
        html: 'Gather around, children, as we\'re going to explain the dreadnought meta in only a few paragraphs. Decades of feeding trillions of ISK just to gather a few simple truths.',
    },
    {
        type: 'quote',
        text: 'Why does everyone fly armor carriers, Mr.ThatCares?',
    },
    {
        type: 'paragraph',
        html: 'Armor is the dominant doctrine for dreadnoughts for one simple reason: neutralizers and midslots.',
    },
    {
        type: 'list',
        items: [
            'Neutralizers turn off guns',
            'Neutralizers turn off active tank modules',
            'Midslots are required to fix capacitor',
        ],
    },
    {
        type: 'paragraph',
        html: 'Everyone wants to make shield dreadnoughts work. Trust me, we\'re Minmatar, after all. Unfortunately, they\'re just worse.',
    },
    {
        type: 'list',
        items: [
            'Shield implant sets are 2× more expensive than armor implant sets',
            'Selectable damage is a bonus, but doesn\'t outweigh the mid slot problem',
        ],
    },
    {
        type: 'paragraph',
        html: 'This is best observed when you see a Phoenix gang or Naglfar gang jump into us. You\'ll notice that we put neutralizers on the secondary — and when we switch to them, they\'re instantly deleted. This is because a Naglfar with capacitor has ~3m EHP, but without capacitor, they have ~1.5m EHP.',
    },
    {
        type: 'paragraph',
        html: 'It sucks. It should be fixed, but it hasn\'t for a long time.',
    },
]

export const shipsLead =
    'One dreadnought is better than zero. If you just joined, use what you can fly — specialize into Rev / RNI / Zir later. Tap a hull for Capitals fittings when we have them.'

export const guidanceLead =
    'In Minmatar Fleet, our guidance is to start with the Revelation. There\'s a few reasons for this.'

export const guidanceReasons = [
    'Revelation Navy Issue is an S-tier dread.',
    'Revelation is a strong T1 dread.',
    'By training capital lasers, you get large lasers. These are common in the subcapital meta.',
]

export const revelationSkillPlan: string[] = [
    'Cybernetics 2',
    'Cybernetics 3',
    'Cybernetics 4',
    'Science 5',
    'Navigation 4',
    'Navigation 5',
    'Warp Drive Operation 3',
    'Warp Drive Operation 4',
    'Warp Drive Operation 5',
    'Jump Drive Operation 1',
    'Jump Drive Operation 2',
    'Jump Drive Operation 3',
    'Jump Drive Operation 4',
    'Jump Drive Operation 5',
    'Jump Drive Calibration 1',
    'Jump Drive Calibration 2',
    'Jump Drive Calibration 3',
    'Jump Drive Calibration 4',
    'Power Grid Management 5',
    'Capacitor Emission Systems 1',
    'Capacitor Emission Systems 2',
    'Capacitor Emission Systems 3',
    'Capacitor Emission Systems 4',
    'Capacitor Emission Systems 5',
    'Capacitor Systems Operation 4',
    'Capacitor Systems Operation 5',
    'Thermodynamics 1',
    'Thermodynamics 2',
    'Thermodynamics 3',
    'Mechanics 4',
    'Thermodynamics 4',
    'Hull Upgrades 4',
    'Hull Upgrades 5',
    'Jump Drive Calibration 5',
    'Biology 1',
    'Long Range Targeting 3',
    'Long Range Targeting 4',
    'Cloaking 1',
    'Kinetic Armor Compensation 1',
    'Thermal Armor Compensation 1',
    'EM Armor Compensation 1',
    'Explosive Armor Compensation 1',
    'EM Armor Compensation 2',
    'Kinetic Armor Compensation 2',
    'Explosive Armor Compensation 2',
    'Thermal Armor Compensation 2',
    'Explosive Armor Compensation 3',
    'Kinetic Armor Compensation 3',
    'Thermal Armor Compensation 3',
    'EM Armor Compensation 3',
    'Kinetic Armor Compensation 4',
    'Explosive Armor Compensation 4',
    'Thermal Armor Compensation 4',
    'EM Armor Compensation 4',
    'Cybernetics 5',
    'Amarr Frigate 2',
    'Amarr Frigate 3',
    'Amarr Destroyer 1',
    'Amarr Destroyer 2',
    'Amarr Destroyer 3',
    'Amarr Cruiser 1',
    'Amarr Cruiser 2',
    'Amarr Cruiser 3',
    'Amarr Battlecruiser 1',
    'Amarr Battlecruiser 2',
    'Amarr Battlecruiser 3',
    'Spaceship Command 4',
    'Amarr Battleship 1',
    'Amarr Battleship 2',
    'Amarr Battleship 3',
    'Weapon Upgrades 3',
    'Weapon Upgrades 4',
    'Advanced Weapon Upgrades 1',
    'Advanced Weapon Upgrades 2',
    'Advanced Weapon Upgrades 3',
    'Advanced Weapon Upgrades 4',
    'Advanced Weapon Upgrades 5',
    'Tactical Weapon Reconfiguration 1',
    'Spaceship Command 5',
    'Advanced Spaceship Command 1',
    'Advanced Spaceship Command 2',
    'Advanced Spaceship Command 3',
    'Advanced Spaceship Command 4',
    'Advanced Spaceship Command 5',
    'Capital Ships 1',
    'Capital Ships 2',
    'Capital Ships 3',
    'Amarr Dreadnought 1',
    'Amarr Dreadnought 2',
    'Amarr Dreadnought 3',
    'Amarr Dreadnought 4',
    'Gunnery 5',
    'Small Energy Turret 2',
    'Small Energy Turret 3',
    'Medium Energy Turret 1',
    'Medium Energy Turret 2',
    'Medium Energy Turret 3',
    'Large Energy Turret 1',
    'Large Energy Turret 2',
    'Large Energy Turret 3',
    'Large Energy Turret 4',
    'Large Energy Turret 5',
    'Capital Energy Turret 1',
    'Capital Energy Turret 2',
    'Capital Energy Turret 3',
    'Capital Energy Turret 4',
    'Capital Energy Turret 5',
    'Motion Prediction 3',
    'Motion Prediction 4',
    'Motion Prediction 5',
    'Capital Pulse Laser Specialization 1',
    'Capital Pulse Laser Specialization 2',
    'Capital Pulse Laser Specialization 3',
    'Capital Pulse Laser Specialization 4',
    'Tactical Weapon Reconfiguration 2',
    'Tactical Weapon Reconfiguration 3',
    'Tactical Weapon Reconfiguration 4',
    'Sharpshooter 3',
    'Trajectory Analysis 2',
    'Trajectory Analysis 3',
    'Trajectory Analysis 4',
    'Tactical Weapon Reconfiguration 5',
    'Rapid Firing 3',
    'Surgical Strike 1',
    'Surgical Strike 2',
    'Surgical Strike 3',
    'Rapid Firing 4',
    'Surgical Strike 4',
    'Sharpshooter 4',
    'Rapid Firing 5',
    'Sharpshooter 5',
    'Surgical Strike 5',
    'Trajectory Analysis 5',
]

export const crosstrainingLead =
    'Since dreads are typically on alts, it\'s important to understand crosstraining. If the character isn\'t sitting in a dread, there are other useful things that it can be doing.'

export const crosstrainingRows: CrosstrainingRow[] = [
    {
        capitals: 'Naglfar / Naglfar Fleet Issue',
        ships: ['Tempest Fleet Issue', 'Panther', 'Tornado'],
    },
    {
        capitals: 'Phoenix / Phoenix Navy Issue',
        ships: ['Typhoon', 'Raven', 'Barghest', 'Scorpion', 'Widow'],
    },
    {
        capitals: 'Moros / Moros Navy Issue',
        ships: ['Vindicator', 'Sin', 'Talos'],
    },
    {
        capitals: 'Revelation / Revelation Navy Issue',
        ships: ['Apocalypse Navy Issue', 'Nightmare', 'Redeemer', 'Oracle'],
    },
]

export const guideSections: GuideSection[] = [
    { id: 'overview', title: 'Overview' },
    { id: 'meta', title: 'Meta' },
    { id: 'ships', title: 'Ships' },
    { id: 'guidance', title: 'Guidance' },
    { id: 'crosstraining', title: 'Crosstraining' },
    { id: 'tribe', title: 'Tribe' },
]

export const dreadHulls: Record<string, CapitalHull> = {
    zirnitra: {
        id: 'zirnitra',
        name: 'Zirnitra',
        shortName: 'Zir',
        shipId: 52907,
    },
    'revelation-navy-issue': {
        id: 'revelation-navy-issue',
        name: 'Revelation Navy Issue',
        shortName: 'RNI',
        shipId: 73790,
    },
    revelation: {
        id: 'revelation',
        name: 'Revelation',
        shortName: 'Rev',
        shipId: 19720,
    },
    'phoenix-navy-issue': {
        id: 'phoenix-navy-issue',
        name: 'Phoenix Navy Issue',
        shortName: 'PNI',
        shipId: 73793,
    },
    phoenix: {
        id: 'phoenix',
        name: 'Phoenix',
        shortName: 'Phoenix',
        shipId: 19726,
    },
    'moros-navy-issue': {
        id: 'moros-navy-issue',
        name: 'Moros Navy Issue',
        shortName: 'MNI',
        shipId: 73792,
    },
    moros: {
        id: 'moros',
        name: 'Moros',
        shortName: 'Moros',
        shipId: 19724,
    },
    'naglfar-fleet-issue': {
        id: 'naglfar-fleet-issue',
        name: 'Naglfar Fleet Issue',
        shortName: 'NFI',
        shipId: 73787,
    },
    naglfar: {
        id: 'naglfar',
        name: 'Naglfar',
        shortName: 'Nag',
        shipId: 19722,
    },
}

export const antiCapitalTier: TierList = {
    id: 'anti-capital-tiers',
    title: 'Anti-capital dreads',
    lead: 'Kill enemy capitals. Zirnitra and Revelation Navy Issue lead — one dread is still better than zero.',
    rows: [
        { tier: 'S', hullIds: ['zirnitra', 'revelation-navy-issue'] },
        { tier: 'C', hullIds: ['revelation', 'naglfar', 'phoenix', 'moros'] },
        { tier: 'LC', hullIds: ['naglfar-fleet-issue', 'moros-navy-issue', 'phoenix-navy-issue'] },
    ],
}

export const hawTier: TierList = {
    id: 'haw-tiers',
    title: 'High-angle dreads',
    lead: 'Delete subcapitals. Phoenix Navy Issue and Moros Navy Issue lead; T1 Phoenix and Naglfar hulls fill common slots.',
    rows: [
        { tier: 'S', hullIds: ['phoenix-navy-issue', 'moros-navy-issue'] },
        { tier: 'C', hullIds: ['phoenix', 'naglfar', 'naglfar-fleet-issue'] },
        { tier: 'LC', hullIds: ['zirnitra', 'revelation-navy-issue', 'revelation', 'moros'] },
    ],
}

export const tierLists: TierList[] = [antiCapitalTier, hawTier]
