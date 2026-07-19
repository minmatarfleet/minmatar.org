import type { ShipGuide } from './types'

export const hookbillGuide: ShipGuide = {
    id: 'hookbill',
    name: 'Caldari Navy Hookbill',
    shortName: 'Hookbill',
    faction: 'Caldari',
    shipId: 17619,
    tagline: 'Five mids and kinetic rockets: the control hull among navy frigates.',
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
                'Two main lines cover each other’s weaknesses. The AB + scram + rocket fit fights at scram range. The MWD + point + light-missile fit lives past 20 km. Pick one before you undock; a mid rack that tries to do both usually fails both.',
                'Most solo rocket fits use an afterburner with scram. A scram shuts a microwarpdrive off, so your prop module has to still work while you are held. Scram and AB travel together; MWD and long point travel together.',
                'Load Scourge. Hull bonuses favor kinetic missiles—Inferno leaves damage on the table. Carry Navy Scourge and Javelin for reach once Rage/Scourge is comfortable.',
            ],
        },
        {
            id: 'scram-kite',
            title: 'Rocket / Scram Line',
            paragraphs: [
                'Start with scram, one web, AB, and three rocket launchers. Hold 7–10 km: close enough for scram and web, far enough to keep transversal. Dual web, tracking disruptor, and faction extenders are upgrades after the basic line is comfortable. Bear\'s favorite line is with a MASB.',
                'Tracking disruptor variants help against turret ships. Swap to a missile disruptor or MASB when local is full of rockets and drones instead of guns.',
            ],
            bullets: [
                'Refit — Control: second web + TD for turret ships.',
                'Refit — Buffer: MSE/BCS for straight DPS races.',
                'Refit — Kite: different ship. MWD, point, light missiles. Do not bolt those onto a rocket mid rack.',
            ],
        },
    ],
    matchups: [
        {
            title: 'Rocket Hookbill',
            fitContext: 'AB scram rocket line.',
            entries: [
                { opponent: 'Blaster Comet', load: 'Scourge Rage', verdict: 'favoured', advice: 'Open range if they land on zero. Your web count usually beats theirs—do not let them close.' },
                { opponent: 'Rail Comet', load: 'Scourge Rage', verdict: 'favoured', advice: 'Both want scram-kite range. Win the control fight; watch for a neut answering your TD.' },
                { opponent: 'Arty Firetail', load: 'Scourge Rage', verdict: 'favoured', advice: 'Similar job, you usually win tank and application. Respect opening alpha.' },
                { opponent: 'AC Firetail', load: 'Scourge Rage', verdict: 'favoured', advice: 'Hold scram-kite range. A neut brawler that hugs you is how you lose.' },
                { opponent: 'Beam Slicer', load: 'Scourge Rage', verdict: 'skill', advice: 'If they establish kite range clean, decline or get scram early. High ground helps.' },
                { opponent: 'Rocket Hookbill mirror', load: 'Scourge Rage', verdict: 'skill', advice: 'Heat, web count, and who blinks on range first.' },
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
                'If you want one navy frigate for most Scout jobs, start here. You win a lot of straight DPS races; you lose mid contests to double-web Hookbills and Firetails.',
                'Most Comets you meet are AB blaster brawlers that want the beacon or a short slide. Keep rails and a neut for ships that sit at 7–10 km.',
                'Scram-kite Comets win by holding 6–8 km. Stay in the fight through the first reload if the tank is still responding; many of these races flip late.',
            ],
        },
        {
            id: 'blaster',
            title: 'Blaster Comet',
            paragraphs: [
                'AB, scram, web, SAAR, double magstab. Carry a damage drone flight and an ECM flight for emergencies. Second web or MWD anti-kite variants exist when local demands them.',
            ],
        },
        {
            id: 'rail',
            title: 'Rail Comet',
            paragraphs: [
                'Same skeleton, 150 mm rails, utility neut. Use Null/Antimatter the way rocket pilots use Rage/Javelin—change ammo when the range changes, not when you are already dead.',
            ],
        },
    ],
    matchups: [
        {
            title: 'Blaster Comet',
            fitContext: 'AB scram/web brawler.',
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
            fitContext: 'Scram-kite with neut.',
            entries: [
                { opponent: 'Rocket Hookbill', load: 'Antimatter', verdict: 'unfavoured', advice: 'Neut helps into TD lines; they still own mid slots. Take it when you have room to work, not when you are already scram-kited badly.' },
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
                'Slot layout pushes you into MWD kiting: five lows, two mids, lasers. Beams project harder when you fly clean; pulses forgive bad transversal.',
                'Cap dies if you leave MWD and point on panic. Save tackle for winning grids. Sticky points into a lost fight is how Slicers die.',
                'Pulse brawl fits exist, but they are secondary. Beacon work belongs on a Comet.',
            ],
        },
        {
            id: 'kite',
            title: 'Kiting Slicer',
            paragraphs: [
                'MWD, warp disruptor, SAAR, double heat sink, double nano, locus rigs. Stay past scram and most webs. Kill with projection; do not orbit into blaster range to “prove” the fit.',
            ],
        },
    ],
    matchups: [
        {
            title: 'Beam Slicer',
            fitContext: 'MWD point kiter.',
            entries: [
                { opponent: 'Blaster Comet', verdict: 'favoured', advice: 'Never enter scram. Stay at point range and apply Multifrequency or X-Ray.' },
                { opponent: 'Rocket Hookbill', verdict: 'favoured', advice: 'Same rule. Scram on you is the failure state.' },
                { opponent: 'Arty Firetail', verdict: 'favoured', advice: 'Win on projection unless they web you into their range.' },
                { opponent: 'Pulse Slicer mirror', verdict: 'skill', advice: 'Beams want range; pulses want to close. Cap wins arguments.' },
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
                'Fast hull with four mids. Double web is how you take range after a slide—something single-web Comets struggle to answer. Expect to lose fair DPS races to Hookbills; win by fight selection and tracking.',
                'Artillery scram/web is the usual solo line: 280s, AB, scram, double web. Point + Javelin rockets for web-kite. Autocannon with a neut trades peak DPS for control and laser cap pressure.',
                'Against pure brawlers, hold range. Against scram-kiters, consider closing with webs. Against clean MWD kiters, leave unless you brought an answer.',
            ],
        },
        {
            id: 'arty',
            title: 'Artillery Firetail',
            paragraphs: [
                'Primary solo line. Tracking is the skill check—keep transversal honest and do not sit still on Quake. Utility rocket launcher carries Rage or Javelin depending on whether you are scram-kiting or web-kiting.',
            ],
        },
        {
            id: 'brawl',
            title: 'Autocannon Firetail',
            paragraphs: [
                'MASB or MSE buffer, neut in the highs, double web still available. Better mid-slot story than a Comet; worse raw hybrid DPS. Use it when you want scram-range fights more than hunting kiters.',
            ],
        },
    ],
    matchups: [
        {
            title: 'Arty Firetail',
            fitContext: 'Scram/web kite artillery.',
            entries: [
                { opponent: 'Rocket Hookbill', load: 'Quake', verdict: 'unfavoured', advice: 'Same role, they usually win tank and application. Take the fights they misplay—do not take mirrors for honor.' },
                { opponent: 'Blaster Comet', load: 'Quake', verdict: 'even', advice: 'Stay out of blaster optimal. Double web is your edge on a slide.' },
                { opponent: 'Rail Comet', load: 'Quake', verdict: 'skill', advice: 'Tracking and heat. Moving ships live longer.' },
                { opponent: 'Beam Slicer', verdict: 'unfavoured', advice: 'Close with webs or leave. Clean kite range is their house.' },
                { opponent: 'AC Firetail', load: 'Quake', verdict: 'favoured', advice: 'Hold kite range against the brawler.' },
                { opponent: 'Rifter', load: 'Quake', verdict: 'favoured', advice: 'Navy control and tank should carry—do not get lazy on tracking.' },
                { opponent: 'Tristan', load: 'Quake', verdict: 'favoured', advice: 'Keep drones at arm’s length; webs help.' },
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
                'Default solo story is Javelin web-kite near the edge of your webs. Scram-kite Rage is the other common line: AB, MSE, scram, and web at mid range without leaning on turret tracking.',
                'Nova uses the explosive damage bonus; keep Scourge and Javelin for resists and reach. Third high is a rail for kite pressure or an autocannon for scram fights.',
            ],
        },
        {
            id: 'web-kite',
            title: 'Web-Kite Vigil Fleet',
            paragraphs: [
                'AB, point, double web, two rockets, 150 mm rail, SAAR. Hold outside their webs and apply Javelin. Common refit: MASB instead of the second web with shield rigs—more tank if you already own range, worse if you have to take a bad slide.',
            ],
        },
        {
            id: 'scram-kite',
            title: 'Scram-Kite Vigil Fleet',
            paragraphs: [
                'AB, MSE, scram, web, two rockets, 150 mm autocannon, double BCS. Rage primary. Anti-kite version swaps the AB for an MWD.',
            ],
        },
    ],
    matchups: [
        {
            title: 'Web-Kite Vigil Fleet',
            fitContext: 'AB point double-web Javelin kite.',
            entries: [
                { opponent: 'Blaster Comet', load: 'Scourge Javelin', verdict: 'favoured', advice: 'Stay outside their web. They cannot make you take a Void race at zero.' },
                { opponent: 'Rocket Hookbill', load: 'Scourge Javelin', verdict: 'favoured', advice: 'Web-kite outside their scram-kite. Do not wander into double web at 8 km.' },
                { opponent: 'Arty Firetail', load: 'Scourge Javelin', verdict: 'favoured', advice: 'Your webs out-range theirs. Hold the long web edge.' },
                { opponent: 'Beam Slicer', load: 'Scourge Javelin', verdict: 'skill', advice: 'Both want range. Cap and heat decide; leave if they own projection clean.' },
                { opponent: 'MASB Breacher', load: 'Scourge Javelin', verdict: 'favoured', advice: 'Same idea as other AB rocket ships—deny their scram-kite range.' },
                { opponent: 'Scram Vigil Fleet Issue', load: 'Scourge Javelin', verdict: 'favoured', advice: 'Web-kite beats the MSE scram line if you never enter scram.' },
            ],
        },
        {
            title: 'Scram-Kite Vigil Fleet',
            fitContext: 'AB MSE scram/web Rage line.',
            entries: [
                { opponent: 'Blaster Comet', load: 'Nova Rage', verdict: 'favoured', advice: 'Hold 6–8 km. Do not take zero.' },
                { opponent: 'Rocket Hookbill', load: 'Nova Rage', verdict: 'unfavoured', advice: 'They usually win mid count and tank. Take misplays only.' },
                { opponent: 'Rail Comet', load: 'Nova Rage', verdict: 'even', advice: 'Similar job. Neut and tracking are their edges; application is yours.' },
                { opponent: 'Beam Slicer', load: 'Nova Rage', verdict: 'bail', advice: 'Do not chase a clean kiter in an MSE scram fit.' },
                { opponent: 'Web Kite Vigil Fleet Issue', load: 'Nova Rage', verdict: 'unfavoured', advice: 'Close past their webs or decline.' },
            ],
        },
    ],
}

export const rifterGuide: ShipGuide = {
    id: 'rifter',
    name: 'Rifter',
    shortName: 'Rifter',
    faction: 'Minmatar',
    shipId: 587,
    tagline: 'Common T1 Scout hull: Firetail habits at T1 prices.',
    bonuses: [
        { label: 'Small Projectile Turret damage', value: '5%' },
        { label: 'Small Projectile Turret tracking speed', value: '7.5%' },
    ],
    roleBonus: 'Flexible projectile platform; common Scout NVY hull for new Matari pilots',
    sections: [
        {
            id: 'overview',
            title: 'Overview',
            paragraphs: [
                'Still one of the most common T1 ships in Scout plexes. Autocannon brawl and artillery scram-kite teach the same ranges you will later fly on a Firetail. You will lose more even trades to navy frigates—treat that as practice cost.',
                'Fit simple. Prop, scram, and web in the mids; one damage scheme; enough tank to survive the first mistake. Dual-prop fantasy fits are how Rifters die confused.',
            ],
        },
        {
            id: 'brawl',
            title: 'Autocannon Rifter',
            paragraphs: [
                'AB, scram, web, gyro, SAAR or buffer. Orbit close, heat when the trade is real, leave when a Hookbill opens range you cannot close.',
            ],
        },
    ],
    matchups: [
        {
            title: 'Autocannon Rifter',
            fitContext: 'AB scram/web brawler.',
            entries: [
                { opponent: 'Blaster Comet', load: 'Phased Plasma', verdict: 'unfavoured', advice: 'Decline unless you have high ground and they misplay. Navy DPS wins fair races.' },
                { opponent: 'Rocket Hookbill', load: 'Phased Plasma', verdict: 'unfavoured', advice: 'Double-web Hookbills own you at scram-kite range. Take the fight only if they land on zero badly.' },
                { opponent: 'Tristan', load: 'Phased Plasma', verdict: 'even', advice: 'Classic T1 trade. Drones and heat decide it.' },
                { opponent: 'Breacher', load: 'Phased Plasma', verdict: 'skill', advice: 'Missile application vs your tank. Do not sit still.' },
                { opponent: 'Rifter mirror', load: 'Phased Plasma', verdict: 'skill', advice: 'Who webs first and who overheats smarter.' },
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
                'Tristans used to define Scout plexes. They still appear constantly, but navy frigates and better missile application have cut the easy wins. Fly it for drone projection and the ability to brawl or hold scram-kite range with rails while drones work.',
                'Watch Hookbill TD lines and neut Comets—both punish lazy drone orbits. Pull drones when you disengage; leaving them on grid turns a retreat into a loss.',
            ],
        },
        {
            id: 'brawl',
            title: 'Brawl / Scram Tristan',
            paragraphs: [
                'AB, scram, web, SAAR, drones out immediately on landing. Hybrid highs are optional DPS; drones are the real weapon. An ECM flight in the bay is a common answer to double-web ships.',
            ],
        },
    ],
    matchups: [
        {
            title: 'Tristan',
            fitContext: 'AB scram drone brawler.',
            entries: [
                { opponent: 'Blaster Comet', verdict: 'unfavoured', advice: 'Navy hybrid DPS usually wins. High ground and ECM drones are your outs.' },
                { opponent: 'Rocket Hookbill', verdict: 'unfavoured', advice: 'Control disadvantage. Do not take it cold on a slide.' },
                { opponent: 'Rifter', verdict: 'even', advice: 'Fair T1 fight—drones vs projectiles.' },
                { opponent: 'Breacher', verdict: 'even', advice: 'Missile vs drones. Application and tank choice matter.' },
                { opponent: 'Beam Slicer', verdict: 'bail', advice: 'Do not chase a clean kiter.' },
            ],
        },
    ],
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
                'Missile combat frig with a real active tank for the class. Default example is one web plus MASB: you keep the booster and SAAR, and you accept one-web control. Drop the MASB for a second web when you want range more than reps.',
                'Navy Hookbills still win many mid contests. Use this hull to practice application, booster timing, and leaving when the range slips.',
            ],
        },
        {
            id: 'scram-kite',
            title: 'MASB Breacher',
            paragraphs: [
                'AB, scram, one web, MASB, rockets, SAAR. Hold 7–10 km. Heat the booster and SAAR for the damage spike, then ease off so you do not waste charges. If Rage is missing an AB target, load Navy Scourge. Keep Javelin for ships that try to leave.',
            ],
        },
    ],
    matchups: [
        {
            title: 'MASB Breacher',
            fitContext: 'AB scram single-web rocket line with MASB + SAAR.',
            entries: [
                { opponent: 'Rifter', load: 'Scourge Rage', verdict: 'favoured', advice: 'Keep range on a close projectile ship. Navy Scourge if Rage is missing.' },
                { opponent: 'Tristan', load: 'Scourge Rage', verdict: 'even', advice: 'Drones vs rockets. Do not let them hug.' },
                { opponent: 'Blaster Comet', load: 'Scourge Rage', verdict: 'unfavoured', advice: 'Navy DPS. High ground helps; sliding cold does not.' },
                { opponent: 'Rocket Hookbill', load: 'Scourge Rage', verdict: 'unfavoured', advice: 'Same role, more mids on their side.' },
                { opponent: 'Arty Firetail', load: 'Scourge Rage', verdict: 'unfavoured', advice: 'Navy control and projection. Take misplays only.' },
            ],
        },
    ],
}

export const shipGuides: ShipGuide[] = [
    hookbillGuide,
    cometGuide,
    slicerGuide,
    firetailGuide,
    vigilFleetGuide,
    rifterGuide,
    tristanGuide,
    breacherGuide,
]
