import type { ShipGuide } from './types'

export const hookbillGuide: ShipGuide = {
    id: 'hookbill',
    name: 'Caldari Navy Hookbill',
    shortName: 'Hookbill',
    faction: 'Caldari',
    shipId: 17619,
    tagline: 'The control king — generally no matchup it can\'t take on high ground.',
    bonuses: [
        { label: 'Light Missile and Rocket damage', value: '5%' },
        { label: 'Light Missile and Rocket max velocity', value: '10%' },
    ],
    roleBonus: 'Built for light missiles and rockets; kinetic (Scourge) is the ammo that matches the hull',
    sections: [
        {
            id: 'overview',
            title: 'Overview',
            paragraphs: [
                'The control king — there\'s generally not a matchup that the Caldari Navy Hookbill can\'t take on high ground. Most rocket fits rock an afterburner, and there are a few variants on tank. Load Scourge, as that\'s what the hull is bonused for.',
                'There are some light missile fittings as well, but they won\'t be included in this guide.',
            ],
        },
    ],
    matchups: [
        {
            title: 'Rocket Hookbill',
            entries: [
                { opponent: 'Blaster Comet', load: 'Scourge Rage', verdict: 'favoured', advice: 'Pull range and hold them at the edge, don\'t let them get close.' },
                { opponent: 'Rail Comet', load: 'Scourge Rage', verdict: 'favoured', advice: 'Both want the scram-kite range, without a TD this matchup is hard. Watch out for the neut.' },
                { opponent: 'Arty Firetail', load: 'Scourge Rage', verdict: 'favoured', advice: 'Usually an easy win, respect their opening alpha.' },
                { opponent: 'AC Firetail', load: 'Scourge Rage', verdict: 'favoured', advice: 'Hold them at range, neuts at 0km is how you die in this fit.' },
                { opponent: 'Beam Slicer', load: 'Scourge Rage', verdict: 'skill', advice: 'High ground helps.' },
                { opponent: 'Rocket Hookbill mirror', load: 'Scourge Rage', verdict: 'skill', advice: 'Heat and pray to the holy rat.' },
            ],
        },
    ],
}

export const cometGuide: ShipGuide = {
    id: 'comet',
    name: 'Federation Navy Comet',
    shortName: 'Comet',
    faction: 'Gallente',
    shipId: 17841,
    tagline: 'Flexible navy hybrid: covers more Scout archetypes than the other three.',
    bonuses: [
        { label: 'Small Hybrid Turret damage', value: '10%' },
        { label: 'Small Hybrid Turret tracking', value: '7.5%' },
    ],
    roleBonus: 'Hybrid damage and tracking on a 3-3-4 layout with strong armor options',
    sections: [
        {
            id: 'overview',
            title: 'Overview',
            paragraphs: [
                'If you want one navy frigate for most jobs, start here. You\'ll win most of your DPS races, often losing out to things that can double web and keep you at range.',
            ],
        },
    ],
    matchups: [
        {
            title: 'Blaster Comet',
            entries: [
                { opponent: 'Rocket Hookbill', load: 'Void', verdict: 'unfavoured', advice: 'On the beacon you can force a trade. Sliding into a double-web Hookbill at 10 km is usually a loss.' },
                { opponent: 'Rail Comet', load: 'Void', verdict: 'skill', advice: 'Close hard. If they hold scram-kite with Null, you are playing their game.' },
                { opponent: 'Arty Firetail', load: 'Void', verdict: 'even', advice: 'Get under the artillery. Their webs fight your single web—high ground matters.' },
                { opponent: 'AC Firetail', load: 'Void', verdict: 'favoured', advice: 'Win the DPS race if tackle lands clean.' },
                { opponent: 'Beam Slicer', load: 'Void', verdict: 'bail', advice: 'Do not chase a clean kiter in a blaster Comet unless you brought anti-kite props.' },
                { opponent: 'Blaster Comet mirror', load: 'Void', verdict: 'skill', advice: 'Heat, drones, and who webs first.' },
            ],
        },
        {
            title: 'Rail Comet',
            entries: [
                { opponent: 'Rocket Hookbill', load: 'Antimatter', verdict: 'unfavoured', advice: 'If you can get your neut applying, you can usually turn off their TDs.' },
                { opponent: 'Blaster Comet', load: 'Null', verdict: 'favoured', advice: 'Hold scram-kite range. Zero is their win condition.' },
                { opponent: 'Arty Firetail', load: 'Antimatter', verdict: 'favoured', advice: 'Similar range story; your tank and neut help.' },
                { opponent: 'Beam Slicer', verdict: 'skill', advice: 'Scram early or leave. A Slicer that never enters tackle range is not your fight.' },
            ],
        },
    ],
}

export const slicerGuide: ShipGuide = {
    id: 'slicer',
    name: 'Imperial Navy Slicer',
    shortName: 'Slicer',
    faction: 'Amarr',
    shipId: 17703,
    tagline: 'Cheap navy kiter: projection and capacitor on a thin hull.',
    bonuses: [
        { label: 'Small Energy Turret damage', value: '10%' },
        { label: 'Small Energy Turret optimal range', value: '10%' },
    ],
    roleBonus: '3-2-5 layout aimed at MWD kiting with energy turrets',
    sections: [
        {
            id: 'overview',
            title: 'Overview',
            paragraphs: [
                'Slot layout pushes you into MWD kiting, and it\'s one of the best kiters in the game. Pulse fits exist, but they\'re often secondary — just fly a Comet.',
                'Everything is about conserving your capacitor. Don\'t use your disruptor the entire fight, use it when you\'re closing the fight.',
            ],
        },
    ],
    matchups: [
        {
            title: 'Beam Slicer',
            entries: [
                { opponent: 'Blaster Comet', verdict: 'favoured', advice: 'Never enter scram. Stay at point range and apply Multifrequency or X-Ray.' },
                { opponent: 'Rocket Hookbill', verdict: 'favoured', advice: 'Same rule. Scram on you is the failure state.' },
                { opponent: 'Arty Firetail', verdict: 'favoured', advice: 'Win on projection unless they web you into their range.' },
                { opponent: 'AC Firetail', verdict: 'favoured', advice: 'Kite clean; leave anti-kite fits alone.' },
            ],
        },
    ],
}

export const firetailGuide: ShipGuide = {
    id: 'firetail',
    name: 'Republic Fleet Firetail',
    shortName: 'Firetail',
    faction: 'Minmatar',
    shipId: 17812,
    tagline: 'Speed and double web: weak on paper, useful when you pick fights.',
    bonuses: [
        { label: 'Small Projectile Turret damage', value: '5%' },
        { label: 'Small Projectile Turret tracking speed', value: '7.5%' },
        { label: 'Small Projectile Turret falloff', value: '5%' },
    ],
    roleBonus: '3-4-3 layout with projectile damage, tracking, and falloff bonuses',
    sections: [
        {
            id: 'overview',
            title: 'Overview',
            paragraphs: [
                'Fast hull with a few opportunistic options. Expect to lose most DPS races — you\'ll often be winning by choosing your battles carefully and out-tracking your opponent.',
            ],
        },
    ],
    matchups: [
        {
            title: 'Arty Firetail',
            entries: [
                { opponent: 'Rocket Hookbill', load: 'Quake', verdict: 'unfavoured', advice: 'Same job, they usually win tank. Take misplays only.' },
                { opponent: 'Blaster Comet', load: 'Quake', verdict: 'even', advice: 'Stay out of blaster optimal. Double web is your edge.' },
                { opponent: 'Rail Comet', load: 'Quake', verdict: 'skill', advice: 'Keep moving. Tracking and heat decide.' },
                { opponent: 'Beam Slicer', verdict: 'unfavoured', advice: 'Close with webs or leave.' },
                { opponent: 'Web Kite Vigil Fleet Issue', load: 'Quake', verdict: 'unfavoured', advice: 'Their webs out-range yours. Close hard or leave.' },
            ],
        },
    ],
}

export const vigilFleetGuide: ShipGuide = {
    id: 'vigil',
    name: 'Vigil Fleet Issue',
    shortName: 'Vigil Fleet',
    faction: 'Minmatar',
    shipId: 37454,
    tagline: 'Long webs and rocket application on a Minmatar navy EWAR hull.',
    bonuses: [
        { label: 'Rocket explosion velocity', value: '5%' },
        { label: 'Explosive Rocket damage', value: '25%' },
        { label: 'EM / kinetic / thermal Rocket damage', value: '20%' },
    ],
    roleBonus: '50% bonus to Stasis Webifier optimal range; 3-4-3 with two launchers and one turret',
    sections: [
        {
            id: 'overview',
            title: 'Overview',
            paragraphs: [
                'Often the better Minmatar navy solo ship than a Firetail. Role bonus webs reach farther than combat-frigate webs, and the explosion velocity bonus helps Rage apply with a single web.',
            ],
        },
    ],
    matchups: [
        {
            title: 'Web-Kite Vigil Fleet',
            entries: [
                { opponent: 'Blaster Comet', load: 'Scourge Javelin', verdict: 'favoured', advice: 'Stay outside their web. They cannot make you take a Void race at zero.' },
                { opponent: 'Rocket Hookbill', load: 'Scourge Javelin', verdict: 'favoured', advice: 'Web-kite outside their scram-kite. Do not wander into double web at 8 km.' },
                { opponent: 'Arty Firetail', load: 'Scourge Javelin', verdict: 'favoured', advice: 'Your webs out-range theirs. Hold the long web edge.' },
                { opponent: 'Beam Slicer', load: 'Scourge Javelin', verdict: 'skill', advice: 'Both want range. Cap and heat decide; leave if they own projection clean.' },
            ],
        },
    ],
}

export const tristanGuide: ShipGuide = {
    id: 'tristan',
    name: 'Tristan',
    shortName: 'Tristan',
    faction: 'Gallente',
    shipId: 593,
    tagline: 'Drone combat frig: still common, no longer automatic.',
    bonuses: [
        { label: 'Drone damage and hitpoints', value: '10%' },
        { label: 'Small Hybrid Turret damage', value: '5%' },
    ],
    roleBonus: 'Drone boat with hybrid highs; flexible armor or shield tank options',
    sections: [
        {
            id: 'overview',
            title: 'Overview',
            paragraphs: [
                'These still appear constantly, but aren\'t the dominant force that they used to be many years ago. Fly it for drones, farming, and the ability to brawl or kite. Pull drones when you\'re running away — those things are as expensive as the ship!',
            ],
        },
    ],
    matchups: [],
}

export const breacherGuide: ShipGuide = {
    id: 'breacher',
    name: 'Breacher',
    shortName: 'Breacher',
    faction: 'Minmatar',
    shipId: 598,
    tagline: 'Missile combat frig: scram-kite rockets with a stronger T1 tank.',
    bonuses: [
        { label: 'Light Missile and Rocket damage', value: '5%' },
        { label: 'Shield booster amount', value: '7.5%' },
    ],
    roleBonus: 'Missile combat frig with stronger tank options than attack frigates',
    sections: [
        {
            id: 'overview',
            title: 'Overview',
            paragraphs: [
                'BearThatCares\'s favorite ship — versatile for both frigate small gangs and casual fights. There are many refits, but typically they involve active tank and some form of range control.',
                'Hookbill is the obvious next step for anyone who enjoys the Breacher.',
            ],
        },
    ],
    matchups: [],
}

export const shipGuides: ShipGuide[] = [
    hookbillGuide,
    cometGuide,
    slicerGuide,
    firetailGuide,
    vigilFleetGuide,
    tristanGuide,
    breacherGuide,
]
