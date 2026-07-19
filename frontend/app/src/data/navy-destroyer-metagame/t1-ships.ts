import type { ShipGuide } from './types'

/** T1 destroyers — house-style prose; fits from common FW skeletons / losses. */

export const algosGuide: ShipGuide = {
    id: 'algos',
    name: 'Algos',
    shortName: 'Algos',
    faction: 'Gallente',
    shipId: 32872,
    tagline: 'Cheap Gallente destroyer: drones carry DPS while rails or ACs set the range.',
    bonuses: [
        { label: 'Small Hybrid Turret tracking', value: '10%' },
        { label: 'Drone hitpoints', value: '10%' },
        { label: 'Drone damage', value: '10%' },
        { label: 'Drone max velocity', value: '10%' },
    ],
    roleBonus: '50% bonus to Small Hybrid Turret optimal range and falloff',
    sections: [
        {
            id: 'overview',
            title: 'Overview',
            paragraphs: [
                'The Algos is the T1 destroyer you see most after the navy hulls. Two medium drones and three lights mean a large chunk of your DPS does not care which guns you fit—range control and prop choice decide the fight more than hybrid vs projectile.',
                'Solo lines are a 10MN rail web-kite and a close MASB/plate autocannon brawl. For LP grinding and multi-boxing, undock the Farm Algos instead of a duel fit.',
            ],
        },
        {
            id: '10mn',
            title: '10mn Algos',
            paragraphs: [
                'Primary fit: 10mn Algos (example fit below). Overpropped AB, web, point, 75 mm rails, SAAR, drone damage amp. Hold web-kite range and let drones work; rails add pressure once the target is slowed.',
                'If they never tackle you, the race often tips your way. Heat the AB when a scram catches the prop wrong.',
            ],
        },
        {
            id: 'brawl',
            title: 'Brawl Algos',
            paragraphs: [
                'Refit — Brawl: MWD, MASB, scram, 200 mm autocannons, plate + SAAR. Higher close-range DPS; worse into clean kiters. Same drone stack.',
            ],
        },
        {
            id: 'farm',
            title: 'Farm Algos',
            paragraphs: [
                'Farm / multi-box line: triple MSE buffer, double compact DDA, one cheap AC for aggro, CDFE rigs. Drones do the work—swap race for rats. Not a duel fit; switch to 10mn or brawl when you want a real fight.',
            ],
        },
    ],
    matchups: [
        {
            title: '10mn Algos',
            fitContext: 'Overpropped rail/drone web-kite.',
            entries: [
                { opponent: 'AC Thrasher', verdict: 'favoured', advice: 'Hold web range. They want to close; you want time for drones.' },
                { opponent: 'Arty Thrasher (280)', verdict: 'skill', advice: 'Alpha hurts. Stay mobile; leave if the first salvos land clean.' },
                { opponent: 'Neut Dragoon', verdict: 'favoured', advice: 'Stay out of neut range. Their DPS is soft if the cap pressure never starts.' },
                { opponent: 'Brawl Coercer', verdict: 'favoured', advice: 'Hold web range. They want to close under scram; you want time for drones.' },
                { opponent: 'Blaster Catalyst Navy Issue', verdict: 'unfavoured', advice: 'Navy brawler. Decline cold slides; take them only if they misrange hard.' },
                { opponent: '10mn Catalyst Navy Issue', verdict: 'unfavoured', advice: 'Same job, better hull. Pick fights they misplay.' },
                { opponent: '10mn Algos mirror', verdict: 'even', advice: 'Drones, rails, and who holds web first.' },
            ],
        },
        {
            title: 'Brawl Algos',
            fitContext: 'MWD MASB AC brawler.',
            entries: [
                { opponent: 'AC Thrasher', verdict: 'even', advice: 'Scram race. Your drones help; their ACs hit hard.' },
                { opponent: 'Neut Dragoon', verdict: 'unfavoured', advice: 'Cap wall. Nos and short trades only; long orbats lose.' },
                { opponent: 'Brawl Coercer', verdict: 'even', advice: 'Scram race. Lasers track; your drones help if you stay alive.' },
                { opponent: '10mn Algos', verdict: 'skill', advice: 'Close hard on the slide or they kite you out.' },
            ],
        },
    ],
}

export const thrasherT1Guide: ShipGuide = {
    id: 'thrasher-t1',
    name: 'Thrasher',
    shortName: 'Thrasher',
    faction: 'Minmatar',
    shipId: 16242,
    tagline: 'Cheap Minmatar destroyer: artillery deletes frigates; ACs trade at scram.',
    bonuses: [
        { label: 'Small Projectile Turret damage', value: '5%' },
        { label: 'Small Projectile Turret tracking speed', value: '7.5%' },
        { label: 'Small Projectile Turret optimal range', value: '10%' },
    ],
    roleBonus: '50% bonus to Small Projectile Turret optimal range and falloff',
    sections: [
        {
            id: 'overview',
            title: 'Overview',
            paragraphs: [
                'If you fly Matari, this is the cheap hull before a Thrasher Fleet Issue. Artillery wins by alpharing thin frigates before they land control. Autocannons are the line when you expect another destroyer at scram range.',
                'Two mids force hard choices: double web without tackle for 280 volleys, or scram + tank for AC brawls. 10MN 250 mm kite fits exist when you want tackle and a longer fight.',
            ],
        },
        {
            id: 'arty',
            title: 'Arty Thrasher',
            paragraphs: [
                'Primary fit: Arty Thrasher (example fit below). MWD, double web, 280s, gyro, bulkheads. No scram: you win the DPS race or both of you leave. Strong into Scout/Small frigates; awkward into tanky navy destroyers that shrug alpha.',
            ],
        },
        {
            id: 'ac',
            title: 'AC Thrasher',
            paragraphs: [
                'Refit — AC: MWD, MSE, scram, 200 mm autocannons, neut, gyros. Better destroyer duel than 280 gank; worse into frigates that hold you at 8–10 km.',
            ],
        },
    ],
    matchups: [
        {
            title: 'Arty Thrasher',
            fitContext: '280 double-web, no scram.',
            entries: [
                { opponent: 'Federation Navy Comet / Hookbill (frigate)', verdict: 'favoured', advice: 'This is the fit’s job. Land webs, volley, do not let them hug for free.' },
                { opponent: 'AC Thrasher', verdict: 'skill', advice: 'Alpha vs sustained. Keep range; a scram AC that closes wins the long race.' },
                { opponent: '10mn Algos', verdict: 'skill', advice: 'Kill drones / track rails. If the fight goes long, they may grind you.' },
                { opponent: 'Neut Dragoon', verdict: 'skill', advice: 'Burst them before neuts cycle you dry. Leaving mid-fight is fine.' },
                { opponent: 'Blaster Catalyst Navy Issue', verdict: 'unfavoured', advice: 'Navy tank shrugs alpha. Decline unless they land poorly.' },
                { opponent: 'AC Thrasher Fleet Issue', verdict: 'unfavoured', advice: 'Same role, better hull. Expect to lose even trades.' },
            ],
        },
        {
            title: 'AC Thrasher',
            fitContext: 'MWD MSE scram AC.',
            entries: [
                { opponent: 'Brawl Algos', verdict: 'even', advice: 'Scram and heat. Watch drones.' },
                { opponent: 'Neut Dragoon', verdict: 'unfavoured', advice: 'Cap pressure ends AC fits. Short fight or leave.' },
                { opponent: 'Arty Thrasher', verdict: 'skill', advice: 'Close under the artillery.' },
                { opponent: 'Blaster Catalyst Navy Issue', verdict: 'unfavoured', advice: 'Navy buffer and DPS. High ground and a mistake required.' },
            ],
        },
    ],
}

export const coercerT1Guide: ShipGuide = {
    id: 'coercer-t1',
    name: 'Coercer',
    shortName: 'Coercer',
    faction: 'Amarr',
    shipId: 16236,
    tagline: 'Cheap Amarr destroyer: eight lasers, two mids, MWD + scram pulse brawl.',
    bonuses: [
        { label: 'Small Energy Turret tracking', value: '10%' },
        { label: 'Small Energy Turret capacitor use', value: '10% reduction' },
        { label: 'Small Energy Turret optimal range', value: '10%' },
    ],
    roleBonus: '50% bonus to Small Energy Turret optimal range and falloff',
    sections: [
        {
            id: 'overview',
            title: 'Overview',
            paragraphs: [
                'Lasers track well and reach farther than most T1 gun fits, so the Coercer still shows up for cheap. Two mids mean tank + tackle leaves no web—the usual solo line is an MWD scram pulse brawl.',
                'Dual Light Pulses with a 400 mm plate are the common FW duel fit. Scorch when you need reach under point; Conflag or Multifreq once you are in their face.',
            ],
        },
        {
            id: 'brawl',
            title: 'Brawl Coercer',
            paragraphs: [
                'Primary fit: Brawl Coercer (example fit below). MWD, scram, eight Dual Light Pulse IIs, plate + coating, triple Trimark. Land scram, control transversal, heat the MWD on the close.',
            ],
        },
    ],
    matchups: [
        {
            title: 'Brawl Coercer',
            fitContext: 'MWD scram Dual Light Pulse plate.',
            entries: [
                { opponent: 'AC Thrasher', verdict: 'favoured', advice: 'Scram race. Tracking and tank usually win even trades.' },
                { opponent: '10mn Algos', verdict: 'skill', advice: 'Close the slide or they kite. Do not orbit at their web range.' },
                { opponent: 'Neut Dragoon', verdict: 'unfavoured', advice: 'Cap wall. Short burn or leave before neuts stick.' },
                { opponent: 'Blaster Catalyst Navy Issue', verdict: 'unfavoured', advice: 'Navy hull out-tanks you. Decline unless they misrange hard.' },
                { opponent: 'Beam Coercer Navy Issue', verdict: 'bail', advice: 'Do not punch a navy laser boat holding range.' },
            ],
        },
    ],
}

export const dragoonGuide: ShipGuide = {
    id: 'dragoon',
    name: 'Dragoon',
    shortName: 'Dragoon',
    faction: 'Amarr',
    shipId: 32874,
    tagline: 'Cap warfare destroyer: three small neuts turn fights off—if they take them.',
    bonuses: [
        { label: 'Drone hitpoints / damage / max velocity', value: '10%' },
        { label: 'Energy Neutralizer / Nosferatu optimal and falloff', value: '20%' },
    ],
    roleBonus: 'Drone and capacitor-warfare focused Amarr T1 destroyer (5-3-4)',
    sections: [
        {
            id: 'overview',
            title: 'Overview',
            paragraphs: [
                'You win on capacitor, not DPS. Three small neuts with a compact cap booster shut down active tanks, MWDs, and laser boats that stay too long. Raw damage is mediocre; expect people to decline once they d-scan the hull.',
                'Solo fits put three neuts and two light guns in the highs, MWD + cap booster + scram in the mids, and either a plate or SAAR + drone amps in the lows. Scram and point are interchangeable.',
            ],
        },
        {
            id: 'brawl',
            title: 'Neut Dragoon',
            paragraphs: [
                'Primary fit: Neut Dragoon (example fit below). Plate + drone amp for longer trades. Damage-leaning refits drop the plate for a second drone amp and SAAR when you already own the scram.',
            ],
        },
    ],
    matchups: [
        {
            title: 'Neut Dragoon',
            fitContext: 'Three small neuts, MWD scram.',
            entries: [
                { opponent: 'AC Thrasher', verdict: 'favoured', advice: 'Cap them out, then grind. Do not let them volley you down before cycle three.' },
                { opponent: 'Brawl Algos', verdict: 'favoured', advice: 'Same story. Watch drones while neuts land.' },
                { opponent: '10mn Algos', verdict: 'unfavoured', advice: 'They may never enter neut range. Decline or force a scramble.' },
                { opponent: 'Brawl Coercer', verdict: 'favoured', advice: 'Cap pressure ends pulse fits that stay too long. Establish neuts early.' },
                { opponent: 'Pulse Coercer Navy Issue', verdict: 'unfavoured', advice: 'Navy laser + tank. Cap helps; DPS usually does not.' },
                { opponent: '2X Neut Coercer Navy Issue', verdict: 'unfavoured', advice: 'They brought more neuts and more hull.' },
                { opponent: 'Neut Dragoon mirror', verdict: 'skill', advice: 'Who cycles first and who heats the booster wrong.' },
            ],
        },
    ],
}
