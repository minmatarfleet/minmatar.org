import type { ShipGuide } from './types'

export const arbitratorGuide: ShipGuide = {
    id: 'arbitrator',
    name: 'Arbitrator',
    shortName: 'Arby',
    faction: 'Amarr',
    shipId: 628,
    tagline: 'Drone DPS with a flexible layout: kite, AB brawl, or TD support.',
    bonuses: [
        { label: 'Drone damage and hitpoints', value: '10%' },
        { label: 'Tracking Disruptor effectiveness', value: '7.5%' },
    ],
    roleBonus: 'Drone damage platform with strong Tracking Disruptor bonuses',
    sections: [
        {
            id: 'overview',
            title: 'Overview',
            paragraphs: [
                'One of the strongest overall T1 cruisers on the list: drones carry the DPS, and the slot layout lets you choose kite, brawl, or gang support without changing hulls. Fitting space is forgiving. Speed is not — be wary of cruisers that can ram you.',
            ],
        },
        {
            id: 'long-point-kite',
            title: 'Long Point Arbitrator',
            paragraphs: [
                'Shield and armor are both viable. Shield pushes DPS and often drops the TD for missile highs; armor keeps the TD and accepts worse speed. Drones do the work at range.',
            ],
        },
        {
            id: 'brawl',
            title: 'Brawl Arbitrator',
            paragraphs: [
                'Abuse blaster and laser boats that have to apply through disruptors and neutralizers.',
            ],
        },
        {
            id: 'td-support',
            title: 'TD Support Arbitrator',
            paragraphs: [
                'Great for defending plexes, although you generally won\'t get many kills solo. Use this to learn the basics, capture some complexes, and perhaps participate in a small gang.',
            ],
        },
    ],
    matchups: [
        {
            title: 'Long Point Arbitrator',
            fitContext: 'Shield XLASB long-point drone kite with light missiles.',
            entries: [
                { opponent: 'Pulse Maller', verdict: 'favoured', advice: 'Hold range; drones and projected control do the work.' },
                { opponent: 'Polarized Augoror Navy Issue', verdict: 'favoured', advice: 'They are slow. Stay at point and grind.' },
                { opponent: 'AB XLASB Stabber', verdict: 'favoured', advice: 'Lower DPS line — do not greed into scram range.' },
                { opponent: 'HAM Caracal Navy Issue', verdict: 'favoured', advice: 'They want scramble. Deny the close.' },
                { opponent: 'Blaster Exequror Navy Issue', verdict: 'bail', advice: 'They catch you. Leave before the ram lands.' },
                { opponent: 'Dual Prop Scythe Fleet Issue', verdict: 'unfavoured', advice: 'Speed and leave tools win. Bail early.' },
                { opponent: 'Dual Prop Stabber Fleet Issue', verdict: 'unfavoured', advice: 'Same story — do not get rammed.' },
            ],
        },
        {
            title: 'Brawl Arbitrator',
            fitContext: '100MN AB shield buffer, LMLs, small neut, drones.',
            entries: [
                { opponent: 'Polarized Augoror Navy Issue', verdict: 'favoured', advice: 'Neuts and drones buy time while their polarized race burns them.' },
                { opponent: 'Beam Omen', verdict: 'favoured', advice: 'Active laser trade into your buffer. Hold zero and grind.' },
                { opponent: 'Blaster Exequror Navy Issue', verdict: 'skill', advice: 'Possible if you establish control early. Do not ego a clean Neutron open.' },
                { opponent: 'Dual Rep Vexor Navy Issue', verdict: 'bail', advice: 'Do not take this for fun. Warp.' },
                { opponent: 'Dual Prop Stabber Fleet Issue', verdict: 'skill', advice: 'Very close. Respect their dual-prop leave.' },
                { opponent: 'Dual Prop Scythe Fleet Issue', verdict: 'skill', advice: 'Close. Respect XLASB and AB out.' },
            ],
        },
    ],
}

export const augniGuide: ShipGuide = {
    id: 'augni',
    name: 'Augoror Navy Issue',
    shortName: 'AugNI',
    faction: 'Amarr',
    shipId: 29337,
    tagline: 'Polarized apex predator, or Pulse Augoror Navy Issue when you want to live.',
    bonuses: [
        { label: 'Medium Energy Turret damage', value: '5%' },
        { label: 'Armor hitpoints', value: '5%' },
        { label: 'Energy Nosferatu / Neutralizer amount', value: '10%' },
    ],
    roleBonus: 'Armor combat Navy Issue with energy warfare bonuses',
    sections: [
        {
            id: 'overview',
            title: 'Overview',
            paragraphs: [
                'Strong solo Navy Issue. The hull HP bonus is what makes polarized play real, and the same frame carries a safer Scorch kite with medium neuts. Pick aggression or stay-alive; both are first-rate.',
            ],
        },
        {
            id: 'polarized',
            title: 'Polarized Augoror Navy Issue',
            paragraphs: [
                'Raw HP plus absurd DPS at zero. Sit on the beacon and delete whatever punches in. Best with high ground. Mix drone types into reactive hardeners or you shred yourself.',
            ],
        },
        {
            id: 'kite-pulse',
            title: 'Pulse Augoror Navy Issue',
            paragraphs: [
                'Pulse and Scorch around thirty kilometres. Medium neuts are defensive when someone rams you and offensive when you close. Faster than a VNI; lower risk, lower reward — hard to kill you.',
            ],
        },
    ],
    matchups: [
        {
            title: 'Polarized Augoror Navy Issue',
            fitContext: 'Dual 1600 polarized heavy pulse, scram/web, high ground preferred.',
            entries: [
                { opponent: 'Blaster Exequror Navy Issue', load: 'Conflag', verdict: 'unfavoured', advice: 'Their favour. Do not ego this.' },
                { opponent: 'Dual Rep Vexor Navy Issue', load: 'Conflag', verdict: 'bail', advice: 'Reactive eats polarized DPS. Leave.' },
                { opponent: 'HAM Caracal Navy Issue', load: 'Conflag', verdict: 'favoured', advice: 'Hold the beacon and melt.' },
                { opponent: '2X Neut HAM Osprey Navy Issue', load: 'Conflag', verdict: 'skill', advice: 'Neuts hurt. Win fast or leave before you dry.' },
                { opponent: 'Brawl Arbitrator', load: 'Conflag', verdict: 'favoured', advice: 'Beacon open into a T1 buffer — you should delete them.' },
                { opponent: 'Dual Prop Stabber Fleet Issue', load: 'Conflag', verdict: 'favoured', advice: 'They slide onto you; keep zero and apply.' },
                { opponent: 'Dual Prop Scythe Fleet Issue', load: 'Conflag', verdict: 'favoured', advice: 'Same — punish the punch-in before they AB out.' },
            ],
        },
        {
            title: 'Pulse Augoror Navy Issue',
            fitContext: 'MAAR Scorch pulse ~30 km with double medium neuts and long point.',
            entries: [
                { opponent: 'Dual Rep Vexor Navy Issue', load: 'Scorch', verdict: 'favoured', advice: 'You are faster; do not get webbed down at zero.' },
                { opponent: 'HAM Caracal Navy Issue', load: 'Scorch', verdict: 'favoured', advice: 'Hold mid-band; they want scramble.' },
                { opponent: 'RHML Osprey Navy Issue', load: 'Scorch', verdict: 'favoured', advice: 'Similar job — your neuts help if the race closes.' },
                { opponent: 'Long Point Arbitrator', load: 'Scorch', verdict: 'skill', advice: 'Range discipline. Do not greed into their drones.' },
                { opponent: 'Blaster Exequror Navy Issue', load: 'Scorch', verdict: 'unfavoured', advice: 'Catch tools and speed will find you.' },
                { opponent: 'Dual Prop Scythe Fleet Issue', load: 'Scorch', verdict: 'unfavoured', advice: 'They run you down. Leave early.' },
                { opponent: 'Armor RLML Scythe Fleet Issue', load: 'Scorch', verdict: 'unfavoured', advice: 'Low-commit catcher. Do not sit forever.' },
            ],
        },
    ],
}

export const mallerGuide: ShipGuide = {
    id: 'maller',
    name: 'Maller',
    shortName: 'Maller',
    faction: 'Amarr',
    shipId: 624,
    tagline: 'Underrated pulse brick: eight-hundred plate and real DPS.',
    bonuses: [
        { label: 'Medium Energy Turret damage', value: '5%' },
        { label: 'Armor hitpoints', value: '5%' },
    ],
    roleBonus: 'Armor laser brick with medium energy turret damage bonuses',
    sections: [
        {
            id: 'overview',
            title: 'Overview',
            paragraphs: [
                'Underrated, not underpowered. Think mini Augoror Navy for plex protection and small gang: respectable DPS on a heavy plate without Navy Issue cost.',
            ],
        },
        {
            id: 'pulse-plate',
            title: 'Pulse Maller',
            paragraphs: [
                'Do not max-plate into uselessness — eight hundred with pulse is the line. Soft into neuts and anything that gets under your tracking.',
            ],
        },
    ],
    matchups: [
        {
            title: 'Pulse Maller',
            fitContext: 'AB 800mm plate pulse brick.',
            entries: [
                { opponent: 'AB XLASB Stabber', load: 'Conflag', verdict: 'favoured', advice: 'Hold the plex and apply.' },
                { opponent: 'XLASB HAM Bellicose', load: 'Conflag', verdict: 'favoured', advice: 'T1 buffer race in your favour if you land pulse clean.' },
                { opponent: 'Beam Omen', load: 'Conflag', verdict: 'even', advice: 'Brick versus brick. Tracking and heat decide it.' },
                { opponent: 'Brawl Arbitrator', load: 'Conflag', verdict: 'unfavoured', advice: 'Neuts and drones grind plates. Leave if control sticks.' },
                { opponent: 'Neut Vexor', load: 'Conflag', verdict: 'bail', advice: 'Cap wall ends laser bricks. Warp.' },
                { opponent: 'Blaster Exequror Navy Issue', load: 'Conflag', verdict: 'unfavoured', advice: 'Navy stat check. Disengage or bring friends.' },
                { opponent: 'Polarized Augoror Navy Issue', load: 'Conflag', verdict: 'unfavoured', advice: 'Same hull family, much more damage. Decline.' },
                { opponent: 'Dual Rep Vexor Navy Issue', load: 'Conflag', verdict: 'bail', advice: 'You will not break the active wall.' },
            ],
        },
    ],
}

export const omenGuide: ShipGuide = {
    id: 'omen',
    name: 'Omen',
    shortName: 'Omen',
    faction: 'Amarr',
    shipId: 2006,
    tagline: 'Underrated laser T1: quad lights, kite pulse, and plex snipers.',
    bonuses: [
        { label: 'Medium Energy Turret damage', value: '5%' },
        { label: 'Medium Energy Turret capacitor use', value: '10% reduction' },
    ],
    roleBonus: 'Laser combat cruiser with medium energy turret capacitor efficiency',
    sections: [
        {
            id: 'overview',
            title: 'Overview',
            paragraphs: [
                'Underrated platform. You clear most T1 cruiser and destroyer work; Navy Issues usually end you in a straight trade. Prefer afterburner on the short-range lines for tracking.',
            ],
        },
        {
            id: 'quad-light',
            title: 'Beam Omen',
            paragraphs: [
                'Odd guns: low fitting, short range, high DPS — think dual one-fifty rails for lasers — with room for a sixteen-hundred plate.',
            ],
        },
        {
            id: 'kite-pulse',
            title: 'Pulse Omen',
            paragraphs: [
                'Same idea as Pulse Augoror Navy Issue at T1 budget. Hold range; do not greed into scram.',
            ],
        },
        {
            id: 'beam-sniper',
            title: 'Sniper Omen',
            paragraphs: [
                'Forces people off a plex more than it solos kills. Hard to fit; useful projection in a small gang.',
            ],
        },
    ],
    matchups: [
        {
            title: 'Beam Omen',
            fitContext: '1600 plate, five Beam Omen Lasers, scram/web.',
            entries: [
                { opponent: 'AB XLASB Stabber', load: 'Gleam', verdict: 'favoured', advice: 'Short-range DPS wins if you land the open.' },
                { opponent: 'XLASB HAM Bellicose', load: 'Gleam', verdict: 'even', advice: 'Buffer race. Heat and drones decide it.' },
                { opponent: 'Pulse Maller', load: 'Gleam', verdict: 'even', advice: 'Laser brick mirror. Tracking matters.' },
                { opponent: 'Brawl Arbitrator', load: 'Gleam', verdict: 'unfavoured', advice: 'Neuts buy them time. Do not sit forever.' },
                { opponent: 'Neut Vexor', load: 'Gleam', verdict: 'unfavoured', advice: 'Cap pressure ends you. Leave.' },
                { opponent: 'Blaster Exequror Navy Issue', load: 'Gleam', verdict: 'unfavoured', advice: 'Navy stat check. Leave.' },
                { opponent: 'HAM Caracal Navy Issue', load: 'Gleam', verdict: 'unfavoured', advice: 'Rage buffer wins fair scram trades.' },
            ],
        },
        {
            title: 'Pulse Omen',
            fitContext: 'MWD scram/web heavy pulse — AugNI kite pattern on T1.',
            entries: [
                { opponent: 'AB XLASB Stabber', load: 'Scorch', verdict: 'favoured', advice: 'Hold range; T1 kite should own the open.' },
                { opponent: 'XLASB HAM Bellicose', load: 'Scorch', verdict: 'favoured', advice: 'Deny scramble. Clip them down.' },
                { opponent: 'Long Point Arbitrator', load: 'Scorch', verdict: 'skill', advice: 'Both want point range. Drones versus pulse — heat decides.' },
                { opponent: 'Blaster Exequror Navy Issue', load: 'Scorch', verdict: 'bail', advice: 'They catch Navy kiters. You are thinner.' },
                { opponent: 'Dual Prop Scythe Fleet Issue', load: 'Scorch', verdict: 'bail', advice: 'Do not take the ram in a T1 pulse kite.' },
                { opponent: 'Kite Omen Navy Issue', load: 'Scorch', verdict: 'unfavoured', advice: 'Same job, better hull. Decline even trades.' },
            ],
        },
        {
            title: 'Sniper Omen',
            fitContext: 'Heavy beam long-point plex protector with MAAR.',
            entries: [
                { opponent: 'AB XLASB Stabber', load: 'Aurora', verdict: 'favoured', advice: 'Force them off the plex more than you solo-kill.' },
                { opponent: 'Vulcan Stabber', load: 'Aurora', verdict: 'favoured', advice: 'Projection contest — beams should win if you hold point.' },
                { opponent: 'Blaster Exequror Navy Issue', load: 'Aurora', verdict: 'bail', advice: 'Once they land scram you are done. Warp.' },
                { opponent: 'Armor RLML Scythe Fleet Issue', load: 'Aurora', verdict: 'unfavoured', advice: 'Low-commit catcher with more speed. Leave early.' },
            ],
        },
    ],
}

export const omenniGuide: ShipGuide = {
    id: 'omenni',
    name: 'Omen Navy Issue',
    shortName: 'OmenNI',
    faction: 'Amarr',
    shipId: 17709,
    tagline: 'Mid-range kite is top tier; sniper and pulse fill the gaps.',
    bonuses: [
        { label: 'Medium Energy Turret damage', value: '5%' },
        { label: 'Medium Energy Turret tracking', value: '7.5%' },
        { label: 'Capacitor capacity', value: '5%' },
    ],
    roleBonus: 'Combat Navy Issue with medium energy turret tracking and capacitor',
    sections: [
        {
            id: 'overview',
            title: 'Overview',
            paragraphs: [
                'If you are flying Omen Navy, you are usually kiting at mid range. That line is the hull\'s job. Sniper and pulse exist for plex pressure and frigates respectively.',
            ],
        },
        {
            id: 'mid-kite',
            title: 'Kite Omen Navy Issue',
            paragraphs: [
                'The top solo reason to undock this hull. Hold mid-band with Scorch, manage capacitor, and do not greed point into a scram.',
            ],
        },
        {
            id: 'mid-sniper',
            title: 'Beam Omen Navy Issue',
            paragraphs: [
                'Longer band for plex denial and gang projection.',
            ],
        },
        {
            id: 'pulse',
            title: 'Pulse Omen Navy Issue',
            paragraphs: [
                'Tracking and frigate work when the mid-range kite is the wrong tool.',
            ],
        },
    ],
    matchups: [
        {
            title: 'Kite Omen Navy Issue',
            fitContext: 'MAAR Scorch pulse kite with long point and a small neut.',
            entries: [
                { opponent: 'Brawl Arbitrator', load: 'Scorch', verdict: 'favoured', advice: 'Hold mid; do not greed point into a scram.' },
                { opponent: 'HAM Caracal Navy Issue', load: 'Scorch', verdict: 'favoured', advice: 'Deny scramble. Clip the buffer at range.' },
                { opponent: 'Dual Rep Vexor Navy Issue', load: 'Scorch', verdict: 'favoured', advice: 'Bleed them if you never enter web range.' },
                { opponent: 'Polarized Augoror Navy Issue', load: 'Scorch', verdict: 'favoured', advice: 'They are a beacon brick. Stay out.' },
                { opponent: 'Long Point Arbitrator', load: 'Scorch', verdict: 'skill', advice: 'Mid-band versus long-point drones. Range discipline.' },
                { opponent: 'RHML Osprey Navy Issue', load: 'Scorch', verdict: 'skill', advice: 'Close fight — who holds band first.' },
                { opponent: 'Blaster Exequror Navy Issue', load: 'Scorch', verdict: 'unfavoured', advice: 'Catch tools win. Leave early.' },
                { opponent: 'Dual Prop Scythe Fleet Issue', load: 'Scorch', verdict: 'unfavoured', advice: 'Speed and leave tools. Warp before the ram.' },
                { opponent: 'Armor RLML Scythe Fleet Issue', load: 'Scorch', verdict: 'unfavoured', advice: 'Low-commit catcher. Do not sit forever.' },
            ],
        },
        {
            title: 'Beam Omen Navy Issue',
            fitContext: 'Heavy beam mid-range sniper with long point.',
            entries: [
                { opponent: 'AB XLASB Stabber', load: 'Aurora', verdict: 'favoured', advice: 'Plex denial — force them off the beacon.' },
                { opponent: 'Vulcan Stabber', load: 'Aurora', verdict: 'favoured', advice: 'Projection should carry if you hold point.' },
                { opponent: 'XLASB HAM Bellicose', load: 'Aurora', verdict: 'favoured', advice: 'Same idea — do not let them scramble free.' },
                { opponent: 'Blaster Exequror Navy Issue', load: 'Aurora', verdict: 'bail', advice: 'Once Neutrons land you are dead. Warp.' },
                { opponent: 'Armor RLML Scythe Fleet Issue', load: 'Aurora', verdict: 'unfavoured', advice: 'They out-range-threat and outspeed. Leave early.' },
            ],
        },
        {
            title: 'Pulse Omen Navy Issue',
            fitContext: 'Closer-range pulse for tracking and frigate work.',
            entries: [
                { opponent: 'AB XLASB Stabber', load: 'Conflag', verdict: 'favoured', advice: 'Closer band where tracking helps.' },
                { opponent: 'Brawl Arbitrator', load: 'Conflag', verdict: 'skill', advice: 'Possible if you open clean. Watch neuts.' },
                { opponent: 'Blaster Exequror Navy Issue', load: 'Conflag', verdict: 'unfavoured', advice: 'Neutron race is not your fight.' },
                { opponent: 'Dual Rep Vexor Navy Issue', load: 'Conflag', verdict: 'bail', advice: 'Do not take the reactive wall at pulse range.' },
            ],
        },
    ],
}

export const caracalniGuide: ShipGuide = {
    id: 'caracalni',
    name: 'Caracal Navy Issue',
    shortName: 'CNI',
    faction: 'Caldari',
    shipId: 17634,
    tagline: 'Idiot-proof HAM brawler — top tier for new pilots.',
    bonuses: [
        { label: 'Heavy Assault Missile and Heavy Missile damage', value: '5%' },
        { label: 'Shield boost amount', value: '7.5%' },
    ],
    roleBonus: 'Missile Navy Issue with heavy assault missile damage and shield boost',
    sections: [
        {
            id: 'overview',
            title: 'Overview',
            paragraphs: [
                'Generous fitting, huge buffer, Rage that applies. One of the best "click approach and win" Navy Issues for pilots who need a simple ship that still works at the top of the meta. Skip T1 Caracal — fly this instead.',
            ],
        },
        {
            id: 'ham',
            title: 'HAM Caracal Navy Issue',
            paragraphs: [
                'Full tackle, HAM Rage, fat tank. Soft into dedicated kiters and into VNI reactives you cannot break.',
            ],
        },
    ],
    matchups: [
        {
            title: 'HAM Caracal Navy Issue',
            fitContext: 'Six-HAM shield brawler with scram/web.',
            entries: [
                { opponent: 'Polarized Augoror Navy Issue', load: 'Rage', verdict: 'favoured', advice: 'Scram, apply Rage, win the buffer race.' },
                { opponent: 'Beam Omen', load: 'Rage', verdict: 'favoured', advice: 'Idiot-proof open into a T1 laser brick.' },
                { opponent: 'Brawl Arbitrator', load: 'Rage', verdict: 'favoured', advice: 'Buffer and apply usually carry.' },
                { opponent: 'Dual Prop Stabber Fleet Issue', load: 'Rage', verdict: 'skill', advice: 'Tough buffer race — high ground helps.' },
                { opponent: '2X Neut HAM Osprey Navy Issue', load: 'Rage', verdict: 'unfavoured', advice: 'Their neuts tip the trade. Leave if dry.' },
                { opponent: 'Dual Rep Vexor Navy Issue', load: 'Rage', verdict: 'unfavoured', advice: 'Reactive stalls you. Do not sit forever.' },
                { opponent: 'Long Point Arbitrator', load: 'Rage', verdict: 'unfavoured', advice: 'If they hold range you struggle. Heat and hope, or leave.' },
                { opponent: 'Kite Omen Navy Issue', load: 'Rage', verdict: 'unfavoured', advice: 'Committed kite. You need a misrange to land.' },
                { opponent: 'Armor RLML Scythe Fleet Issue', load: 'Rage', verdict: 'unfavoured', advice: 'Low-commit catcher bleeds you. Decline.' },
            ],
        },
    ],
}

export const ospreyniGuide: ShipGuide = {
    id: 'ospreyni',
    name: 'Osprey Navy Issue',
    shortName: 'OspreyNI',
    faction: 'Caldari',
    shipId: 29340,
    tagline: 'Mixed hardpoints: double-neut HAM and RHML kite.',
    bonuses: [
        { label: 'Heavy Assault Missile and Heavy Missile damage', value: '5%' },
        { label: 'Shield boost amount', value: '7.5%' },
    ],
    roleBonus: 'Missile Navy Issue with utility highs for neuts and projection tools',
    sections: [
        {
            id: 'overview',
            title: 'Overview',
            paragraphs: [
                'Three launchers leave two utility highs, six mids, and four lows. That layout is the hull\'s whole strength. Harder to fly and tighter to fit than Caracal Navy Issue. In solo, the neuts matter more than the raw DPS gap.',
            ],
        },
        {
            id: 'ham-neut',
            title: '2X Neut HAM Osprey Navy Issue',
            paragraphs: [
                'Medium neuts let you take Caracal Navy Issues and put real pressure on Vexor Navy Issue when the trade goes right.',
            ],
        },
        {
            id: 'rhml-kite',
            title: 'RHML Osprey Navy Issue',
            paragraphs: [
                'Damage-per-level clip into kiting cruisers with a very large XLASB tank. Anything that catches you is scary — leave early.',
            ],
        },
    ],
    matchups: [
        {
            title: '2X Neut HAM Osprey Navy Issue',
            fitContext: 'Three HAM launchers and two medium neuts.',
            entries: [
                { opponent: 'HAM Caracal Navy Issue', load: 'Rage', verdict: 'favoured', advice: 'Neuts tip the trade.' },
                { opponent: 'Polarized Augoror Navy Issue', load: 'Rage', verdict: 'favoured', advice: 'Cap pressure plus HAM — finish before they melt you.' },
                { opponent: 'Blaster Exequror Navy Issue', load: 'Rage', verdict: 'skill', advice: 'Neuts help; Neutrons still hurt. High ground matters.' },
                { opponent: 'Dual Rep Vexor Navy Issue', load: 'Rage', verdict: 'skill', advice: 'Possible with neut pressure. Do not scramble yourself.' },
                { opponent: 'Brawl Arbitrator', load: 'Rage', verdict: 'favoured', advice: 'Cap them, then grind.' },
                { opponent: 'Dual Prop Scythe Fleet Issue', load: 'Rage', verdict: 'unfavoured', advice: 'They punch and leave. Do not ego the chase.' },
                { opponent: 'Dual Prop Stabber Fleet Issue', load: 'Rage', verdict: 'skill', advice: 'Winnable if neuts stick. Watch their AB out.' },
            ],
        },
        {
            title: 'RHML Osprey Navy Issue',
            fitContext: 'RHML long-point kite with XLASB.',
            entries: [
                { opponent: 'HAM Caracal Navy Issue', load: 'Fury', verdict: 'favoured', advice: 'Clip into the brawler if you hold point.' },
                { opponent: 'Polarized Augoror Navy Issue', load: 'Fury', verdict: 'favoured', advice: 'Same — deny zero.' },
                { opponent: 'Kite Omen Navy Issue', load: 'Fury', verdict: 'skill', advice: 'Close fight — range discipline decides it.' },
                { opponent: 'Long Point Arbitrator', load: 'Fury', verdict: 'even', advice: 'Missile kite versus drone kite. Heat and drones decide.' },
                { opponent: 'Dual Prop Scythe Fleet Issue', load: 'Fury', verdict: 'bail', advice: 'Primary counter. Do not get caught.' },
                { opponent: 'Dual Prop Stabber Fleet Issue', load: 'Fury', verdict: 'unfavoured', advice: 'They close. Leave early.' },
                { opponent: 'Armor RLML Scythe Fleet Issue', load: 'Fury', verdict: 'bail', advice: 'They are the catcher in this matchup.' },
            ],
        },
    ],
}

export const eniGuide: ShipGuide = {
    id: 'eni',
    name: 'Exequror Navy Issue',
    shortName: 'ENI',
    faction: 'Gallente',
    shipId: 29344,
    tagline: 'Still top tier: free plate feel, scram-edge falloff, Neutrons.',
    bonuses: [
        { label: 'Medium Hybrid Turret damage', value: '5%' },
        { label: 'Armor hitpoints', value: '5%' },
        { label: 'Armor plate mass penalty', value: '5% reduction' },
    ],
    roleBonus: 'Armor hybrid Navy Issue with plate mass reduction and hybrid damage',
    sections: [
        {
            id: 'overview',
            title: 'Overview',
            paragraphs: [
                'Even after the nerfs, still the navy cruiser to beat. Plate mass reduction makes a sixteen-hundred feel nearly free. Falloff keeps Neutrons applying at the edge of scram. Prefer Neutrons over ions: once both ships land scram and web, a bad slingshot ends the fight, and neutrons forgive more.',
            ],
        },
        {
            id: 'blaster',
            title: 'Blaster Exequror Navy Issue',
            paragraphs: [
                'Double web, sixteen-hundred plate, Neutrons, enough speed to close kiters. Soft into VNI active tanks.',
            ],
        },
        {
            id: 'rails',
            title: '250mm Rail Exequror Navy Issue',
            paragraphs: [
                'More useful in a small gang than solo. Good plex defense on the same mid-band profile as other Navy kiters. Tracks cruisers; struggle against smaller hulls.',
            ],
        },
        {
            id: 'dual-plate-electron',
            title: 'Dual Plate Electron Exequror Navy Issue',
            paragraphs: [
                'Solo plexing and militia fleet. Double plate buffer with electrons for frigate and destroyer blobs.',
            ],
        },
    ],
    matchups: [
        {
            title: 'Blaster Exequror Navy Issue',
            fitContext: 'Neutron plate brawler with double web and a small nos.',
            entries: [
                { opponent: 'Polarized Augoror Navy Issue', load: 'Void', verdict: 'favoured', advice: 'Your favour if you land the open clean.' },
                { opponent: 'Pulse Augoror Navy Issue', load: 'Void', verdict: 'favoured', advice: 'You have the speed. Close, scram, apply.' },
                { opponent: 'Kite Omen Navy Issue', load: 'Void', verdict: 'favoured', advice: 'Catch tools win. Punch in before they leave.' },
                { opponent: 'Long Point Arbitrator', load: 'Void', verdict: 'favoured', advice: 'Ram the kite. Do not orbit at their drone comfort.' },
                { opponent: 'RHML Osprey Navy Issue', load: 'Void', verdict: 'favoured', advice: 'Close hard. Their XLASB only buys time.' },
                { opponent: 'Dual Prop Scythe Fleet Issue', load: 'Void', verdict: 'favoured', advice: 'You are the harder trade — force the scram.' },
                { opponent: 'Dual Prop Stabber Fleet Issue', load: 'Void', verdict: 'favoured', advice: 'They cannot speed-tank Neutrons cleanly.' },
                { opponent: 'HAM Caracal Navy Issue', load: 'Void', verdict: 'even', advice: 'Buffer race. High ground and heat decide it.' },
                { opponent: '2X Neut HAM Osprey Navy Issue', load: 'Void', verdict: 'skill', advice: 'Watch neuts. Win fast or leave dry.' },
                { opponent: 'Dual Rep Vexor Navy Issue', load: 'Void', verdict: 'unfavoured', advice: 'They tank you. Do not die for pride.' },
            ],
        },
        {
            title: '250mm Rail Exequror Navy Issue',
            fitContext: '250mm rail plex / gang flex on the ENI tank skeleton.',
            entries: [
                { opponent: 'AB XLASB Stabber', load: 'Spike', verdict: 'favoured', advice: 'Mid-band plex hold clears most low-tier opens.' },
                { opponent: 'Long Point Arbitrator', load: 'Spike', verdict: 'favoured', advice: 'Same mid-band job — rails should pressure.' },
                { opponent: 'Pulse Augoror Navy Issue', load: 'Spike', verdict: 'even', advice: 'Mid-band profile match. Tracking and heat.' },
                { opponent: 'Kite Omen Navy Issue', load: 'Spike', verdict: 'even', advice: 'Same story. Cap and band discipline.' },
                { opponent: 'Dual Rep Vexor Navy Issue', load: 'Spike', verdict: 'skill', advice: 'Bleed if you hold range; do not get webbed to zero.' },
                { opponent: 'Armor RLML Scythe Fleet Issue', load: 'Spike', verdict: 'even', advice: 'Both want low-commit pressure. Leave if they own band.' },
                { opponent: 'Blaster Exequror Navy Issue', load: 'Spike', verdict: 'unfavoured', advice: 'Sister hull with Neutrons — decline the close trade.' },
            ],
        },
        {
            title: 'Dual Plate Electron Exequror Navy Issue',
            fitContext: 'Dual 1600 electron blob / mass-fight line.',
            entries: [
                { opponent: 'AB XLASB Stabber', load: 'Void', verdict: 'favoured', advice: 'Blob buffer wins if they commit into you.' },
                { opponent: 'XLASB HAM Bellicose', load: 'Void', verdict: 'favoured', advice: 'Mass-fight apply into T1 flash tanks.' },
                { opponent: 'Dual Rep Vexor Navy Issue', load: 'Void', verdict: 'unfavoured', advice: 'Solo reactive wall is still not your job.' },
                { opponent: 'Frigate / destroyer blob', verdict: 'favoured', advice: 'Electrons and double plate exist for this.' },
            ],
        },
    ],
}

export const vexorGuide: ShipGuide = {
    id: 'vexor',
    name: 'Vexor',
    shortName: 'Vexor',
    faction: 'Gallente',
    shipId: 626,
    tagline: 'Neut-plate plex defender; blaster trade fit for T1 work.',
    bonuses: [
        { label: 'Drone damage and hitpoints', value: '10%' },
        { label: 'Drone bandwidth', value: 'bonus varies by level' },
    ],
    roleBonus: 'Drone combat cruiser with strong bandwidth and drone damage',
    sections: [
        {
            id: 'overview',
            title: 'Overview',
            paragraphs: [
                'Strong high-ground T1. Soft at punching into kiters, excellent when they punch into you. Cap warfare plus plate wins a lot of zero-range trades. Subpar for organized small-gang damage application — drones derp when the grid is busy.',
            ],
        },
        {
            id: 'neut-plate',
            title: 'Neut Vexor',
            paragraphs: [
                'Sixteen-hundred plate and a neut stack. Caps out many active gunboats that slide in. Prefer defending a plex over chasing.',
            ],
        },
        {
            id: 'blaster-neut',
            title: 'Blaster Vexor',
            paragraphs: [
                'Bulkheaded blaster with a medium neut. Wins most T1 mirror work; Navy Issues still end you.',
            ],
        },
    ],
    matchups: [
        {
            title: 'Neut Vexor',
            fitContext: '1600 plate plex holder with multi-neut highs and heavy drones.',
            entries: [
                { opponent: 'Polarized Augoror Navy Issue', verdict: 'favoured', advice: 'Neuts on, hold zero, grit the buffer.' },
                { opponent: 'Pulse Maller', verdict: 'favoured', advice: 'Cap wall ends laser bricks that slide in.' },
                { opponent: 'Beam Omen', verdict: 'favoured', advice: 'Same — establish neuts early.' },
                { opponent: 'Blaster Exequror Navy Issue', verdict: 'favoured', advice: 'Hold when they punch into you and misplay.' },
                { opponent: 'Brawl Arbitrator', verdict: 'skill', advice: 'T1 control fight. Drones versus neuts.' },
                { opponent: 'Dual Prop Scythe Fleet Issue', verdict: 'even', advice: 'Close — respect leave tools.' },
                { opponent: 'Dual Prop Stabber Fleet Issue', verdict: 'even', advice: 'Same. Do not chase the AB out.' },
                { opponent: 'Long Point Arbitrator', verdict: 'unfavoured', advice: 'You will not catch them. Sit or leave.' },
                { opponent: 'Kite Omen Navy Issue', verdict: 'unfavoured', advice: 'Dedicated kite never enters neut range.' },
                { opponent: 'Armor RLML Scythe Fleet Issue', verdict: 'unfavoured', advice: 'Low-commit pressure outside your job.' },
            ],
        },
        {
            title: 'Blaster Vexor',
            fitContext: 'Neutron + dual mag stab scram brawler with bulkhead rigs.',
            entries: [
                { opponent: 'AB XLASB Stabber', load: 'Void', verdict: 'favoured', advice: 'Wins most T1 mirror work.' },
                { opponent: 'XLASB HAM Bellicose', load: 'Void', verdict: 'favoured', advice: 'Scram race into a T1 missile boat.' },
                { opponent: 'Pulse Maller', load: 'Void', verdict: 'favoured', advice: 'Close and apply. Neuts help if they linger.' },
                { opponent: 'Beam Omen', load: 'Void', verdict: 'favoured', advice: 'Same job.' },
                { opponent: 'Brawl Arbitrator', load: 'Void', verdict: 'skill', advice: 'Control fight. Watch their neut.' },
                { opponent: 'Blaster Exequror Navy Issue', load: 'Void', verdict: 'unfavoured', advice: 'Navy Issue still ends you.' },
                { opponent: 'HAM Caracal Navy Issue', load: 'Void', verdict: 'unfavoured', advice: 'Rage buffer. Decline fair trades.' },
                { opponent: 'Dual Rep Vexor Navy Issue', load: 'Void', verdict: 'bail', advice: 'Sister hull with dual reps. Warp.' },
            ],
        },
    ],
}

export const vniGuide: ShipGuide = {
    id: 'vni',
    name: 'Vexor Navy Issue',
    shortName: 'VNI',
    faction: 'Gallente',
    shipId: 17843,
    tagline: 'Dual-rep landlord: barely loses a scram fight without neuts-plus-DPS.',
    bonuses: [
        { label: 'Drone damage and hitpoints', value: '10%' },
        { label: 'Armor repairer amount', value: '7.5%' },
    ],
    roleBonus: 'Drone Navy Issue with armor repair amount bonuses',
    sections: [
        {
            id: 'overview',
            title: 'Overview',
            paragraphs: [
                'The hull other people hate punching into. Once you land scram, you win most straight trades. Kiters can theoretically bleed you, but holding two kilometres a second for the whole booster stack is hard. Double cap booster for solo. Weak once frigates and destroyers defang your drones.',
            ],
        },
        {
            id: 'dual-rep',
            title: 'Dual Rep Vexor Navy Issue',
            paragraphs: [
                'Dual reps, reactive, prefer double cap booster. Cheap drugs make the active wall absurd. Heavy neut stacks are the honest answer — and even then the trade is messy.',
            ],
        },
    ],
    matchups: [
        {
            title: 'Dual Rep Vexor Navy Issue',
            fitContext: 'Dual-rep reactive electron with double medium cap boosters.',
            entries: [
                { opponent: 'Blaster Exequror Navy Issue', load: 'Void', verdict: 'favoured', advice: 'Hold close, manage boosters, win the bleed.' },
                { opponent: 'Polarized Augoror Navy Issue', load: 'Void', verdict: 'favoured', advice: 'Reactive eats polarized. Scram clean and smirk.' },
                { opponent: 'HAM Caracal Navy Issue', load: 'Void', verdict: 'favoured', advice: 'Once you land scram you win most straight trades.' },
                { opponent: 'Dual Prop Stabber Fleet Issue', load: 'Void', verdict: 'favoured', advice: 'Do not let them speed-tank forever — hold scramble.' },
                { opponent: 'Brawl Arbitrator', load: 'Void', verdict: 'favoured', advice: 'T1 control into your wall. Manage boosters.' },
                { opponent: '2X Neut HAM Osprey Navy Issue', load: 'Void', verdict: 'skill', advice: 'Heavy neut + DPS is the honest answer — and even then messy.' },
                { opponent: 'Neut Vexor', load: 'Void', verdict: 'skill', advice: 'T1 neut stack can pressure. Win the cap race or leave.' },
                { opponent: 'Kite Omen Navy Issue', load: 'Void', verdict: 'skill', advice: 'They can bleed you in theory — holding 2 km/s for the whole stack is hard.' },
                { opponent: 'Armor RLML Scythe Fleet Issue', load: 'Void', verdict: 'skill', advice: 'Low-commit kite. Force a scramble or decline.' },
                { opponent: 'Frigate / destroyer dogpile', verdict: 'unfavoured', advice: 'They defang drones. Warp before the swarm finishes you.' },
            ],
        },
    ],
}

export const bellicoseGuide: ShipGuide = {
    id: 'bellicose',
    name: 'Bellicose',
    shortName: 'Bellicose',
    faction: 'Minmatar',
    shipId: 630,
    tagline: 'Cheaper Caracal energy: HAM grinders and XLASB plex work.',
    bonuses: [
        { label: 'Missile launcher rate of fire', value: '5% reduction' },
        { label: 'Target painter effectiveness', value: '7.5%' },
    ],
    roleBonus: 'Missile T1 cruiser with launcher rate of fire and target painter bonuses',
    sections: [
        {
            id: 'overview',
            title: 'Overview',
            paragraphs: [
                'Contract workhorse. HAM plus point and drones for simple fleet and meat-grinder work; XLASB for high-ground plex defense. Not the sharpest pure solo hull, but it stocks cleanly and wins the fights T1 should win.',
            ],
        },
        {
            id: 'ham',
            title: 'HAM Bellicose',
            paragraphs: [
                'Idiot-proof apply for gangs and meat-grinders. Skip it when you want dedicated solo work.',
            ],
        },
        {
            id: 'xlsb',
            title: 'XLASB HAM Bellicose',
            paragraphs: [
                'Plex protector with flash tank. Covers most T1 and small-hull gates; can punish faction kiters that greed into you.',
            ],
        },
    ],
    matchups: [
        {
            title: 'HAM Bellicose',
            fitContext: 'Four-HAM shield scram brawler with light drones.',
            entries: [
                { opponent: 'AB XLASB Stabber', load: 'Rage', verdict: 'favoured', advice: 'Idiot-proof apply for gangs and meat-grinders.' },
                { opponent: 'Pulse Maller', load: 'Rage', verdict: 'favoured', advice: 'T1 laser brick — scramble and grind.' },
                { opponent: 'Beam Omen', load: 'Rage', verdict: 'favoured', advice: 'Same job.' },
                { opponent: 'Brawl Arbitrator', load: 'Rage', verdict: 'even', advice: 'Control versus buffer. Heat decides.' },
                { opponent: 'Blaster Exequror Navy Issue', load: 'Rage', verdict: 'unfavoured', advice: 'Not your solo fight. Decline.' },
                { opponent: 'HAM Caracal Navy Issue', load: 'Rage', verdict: 'unfavoured', advice: 'Same role, better hull.' },
            ],
        },
        {
            title: 'XLASB HAM Bellicose',
            fitContext: 'XLASB HAM Bellicose plex protector — trade a LSE for the ancillary.',
            entries: [
                { opponent: 'AB XLASB Stabber', load: 'Rage', verdict: 'even', advice: 'Flash-tank beacon fight. Boost correctly.' },
                { opponent: 'Pulse Maller', load: 'Rage', verdict: 'favoured', advice: 'Hold the beacon; cover most T1 opens.' },
                { opponent: 'Beam Omen', load: 'Rage', verdict: 'even', advice: 'Buffer race. Do not overheat incorrectly.' },
                { opponent: 'Brawl Arbitrator', load: 'Rage', verdict: 'even', advice: 'Close T1 control fight.' },
                { opponent: 'Neut Vexor', load: 'Rage', verdict: 'unfavoured', advice: 'Neuts grind flash tanks. Leave if dry.' },
                { opponent: 'Kite Omen Navy Issue', load: 'Rage', verdict: 'skill', advice: 'Can punish greedy point holds if they slide in wrong.' },
                { opponent: 'Dual Prop Stabber Fleet Issue', load: 'Rage', verdict: 'skill', advice: 'Close if skill gaps are large. Respect leave tools.' },
                { opponent: 'Dual Prop Scythe Fleet Issue', load: 'Rage', verdict: 'skill', advice: 'Same — flash tank versus leave-insurance.' },
            ],
        },
    ],
}

export const scythefiGuide: ShipGuide = {
    id: 'scythefi',
    name: 'Scythe Fleet Issue',
    shortName: 'ScytheFI',
    faction: 'Minmatar',
    shipId: 29336,
    tagline: 'Dual-prop leave-machine; armor RLML for low-commit plex (XLASB RLML refit).',
    bonuses: [
        { label: 'Missile damage', value: '5%' },
        { label: 'Shield boost amount', value: '7.5%' },
    ],
    roleBonus: 'Fleet Issue combat hull with missile damage and shield boost',
    sections: [
        {
            id: 'overview',
            title: 'Overview',
            paragraphs: [
                'Nearly three kilometres a second cold on dual prop with a flash tank that lets you commit, then leave. That leave button is the hull\'s whole identity.',
            ],
        },
        {
            id: 'dual-prop-ac',
            title: 'Dual Prop Scythe Fleet Issue',
            paragraphs: [
                'Run people down on microwarpdrive; afterburner out when the tank collapses. Default punch-and-leave solo tool.',
            ],
        },
        {
            id: 'rlml-armor',
            title: 'Armor RLML Scythe Fleet Issue',
            paragraphs: [
                'Armor tank, medium neut, roughly sixty kilometres of low-commit pressure — the common solo RLML meta line. Excellent plex defense: faster than almost everything, and filthy against frigate tackle gangs. Refit: RLML XLASB Scythe Fleet Issue for the shield flash-tank kite when you want XLASB leave tools instead of plate/MAAR.',
            ],
        },
    ],
    matchups: [
        {
            title: 'Dual Prop Scythe Fleet Issue',
            fitContext: 'MWD + AB XLASB Stabber leave-insurance with Dual 180mm ACs.',
            entries: [
                { opponent: 'HAM Caracal Navy Issue', load: 'Hail', verdict: 'favoured', advice: 'Punch in; leave if the trade turns.' },
                { opponent: '2X Neut HAM Osprey Navy Issue', load: 'Hail', verdict: 'favoured', advice: 'Comfortable if you pick the trade and AB out.' },
                { opponent: 'RHML Osprey Navy Issue', load: 'Hail', verdict: 'favoured', advice: 'You are the catcher. Run them down.' },
                { opponent: 'Kite Omen Navy Issue', load: 'Hail', verdict: 'favoured', advice: 'Close the kite; leave if wrong.' },
                { opponent: 'Pulse Augoror Navy Issue', load: 'Hail', verdict: 'favoured', advice: 'Same — speed is the identity.' },
                { opponent: 'Polarized Augoror Navy Issue', load: 'Hail', verdict: 'favoured', advice: 'Punch the beacon brick and AB out if polarized wins.' },
                { opponent: 'Brawl Arbitrator', load: 'Hail', verdict: 'favoured', advice: 'Free trades into T1 control.' },
                { opponent: 'XLASB HAM Bellicose', load: 'Hail', verdict: 'favoured', advice: 'Take the free open; leave if flash tank holds.' },
                { opponent: 'Blaster Exequror Navy Issue', load: 'Hail', verdict: 'unfavoured', advice: 'Respect them. Take free shots or warp.' },
                { opponent: 'Dual Prop Stabber Fleet Issue', load: 'Hail', verdict: 'unfavoured', advice: 'Soft into Stabber Fleet. Respect the web and plate.' },
                { opponent: 'Dual Rep Vexor Navy Issue', load: 'Hail', verdict: 'skill', advice: 'Possible if you never commit past leave. Do not sit in reps.' },
            ],
        },
        {
            title: 'Armor RLML Scythe Fleet Issue',
            fitContext: 'Low-commit ~60 km RLML with medium neut. Refit: RLML XLASB Scythe Fleet Issue.',
            entries: [
                { opponent: 'RHML Osprey Navy Issue', load: 'Fury', verdict: 'favoured', advice: 'You are the catcher in this matchup.' },
                { opponent: 'Long Point Arbitrator', load: 'Fury', verdict: 'favoured', advice: 'Low-commit pressure with speed.' },
                { opponent: 'Kite Omen Navy Issue', load: 'Fury', verdict: 'favoured', advice: 'Same mid-band story — you usually force the leave.' },
                { opponent: 'Pulse Augoror Navy Issue', load: 'Fury', verdict: 'favoured', advice: 'Faster than almost everything on this line.' },
                { opponent: 'HAM Caracal Navy Issue', load: 'Fury', verdict: 'favoured', advice: 'Clip the brawler; do not greed into scramble.' },
                { opponent: '250mm Rail Exequror Navy Issue', load: 'Fury', verdict: 'even', advice: 'Low-commit versus mid-band rails.' },
                { opponent: 'Vulcan Stabber', load: 'Fury', verdict: 'favoured', advice: 'Projection and speed should carry.' },
                { opponent: 'Frigate / destroyer tackle', verdict: 'favoured', advice: 'Neut the landers; clip them down.' },
                { opponent: 'Blaster Exequror Navy Issue', load: 'Fury', verdict: 'unfavoured', advice: 'If they punch clean, leave — do not invent a dual-prop race.' },
            ],
        },
        {
            title: 'RLML XLASB Scythe Fleet Issue',
            fitContext: 'Four RLML + XLASB long-point kite with a small neut (Armor RLML Scythe Fleet Issue refit).',
            entries: [
                { opponent: 'HAM Caracal Navy Issue', load: 'Fury', verdict: 'favoured', advice: 'Range trade when you do not want the dual-prop AC commit.' },
                { opponent: 'Long Point Arbitrator', load: 'Fury', verdict: 'skill', advice: 'Missile versus drone kite. Band discipline.' },
                { opponent: 'Kite Omen Navy Issue', load: 'Fury', verdict: 'skill', advice: 'Projection contest. Leave if they own mid-band.' },
                { opponent: 'Blaster Exequror Navy Issue', load: 'Fury', verdict: 'unfavoured', advice: 'Once they land you are in trouble. Warp.' },
                { opponent: 'Armor RLML Scythe Fleet Issue', load: 'Fury', verdict: 'skill', advice: 'Sister line — armor has the neut reach.' },
            ],
        },
    ],
}

export const stabberGuide: ShipGuide = {
    id: 'stabber',
    name: 'Stabber',
    shortName: 'Stabber',
    faction: 'Minmatar',
    shipId: 622,
    tagline: 'AB XLASB plex hold and Vulcan half-kite — never MWD scram.',
    bonuses: [
        { label: 'Medium Projectile Turret damage', value: '5%' },
        { label: 'Max velocity', value: '5%' },
    ],
    roleBonus: 'Projectile T1 cruiser with turret damage and velocity bonuses',
    sections: [
        {
            id: 'overview',
            title: 'Overview',
            paragraphs: [
                'Same job family as Bellicose for plex defense, with projectile tracking instead of missiles. Strong against T1 cruisers; can get under laser boats. Never fit microwarpdrive plus scram for solo — you will lose more than you win, even into Navy kiters, because the tank is too thin.',
            ],
        },
        {
            id: 'xlsb',
            title: 'AB XLASB Stabber',
            paragraphs: [
                'Plex protector with real brawl stats and neut highs for frigate and destroyer gangs. Some Scythe Fleet Issues are stealable if you catch scram on a microwarpdrive fit.',
            ],
        },
        {
            id: 'vulcan-kite',
            title: 'Vulcan Stabber',
            paragraphs: [
                'Shield kite with point and a rapid light. Stay at range, defend the plex, die for the kill only when you choose to.',
            ],
        },
    ],
    matchups: [
        {
            title: 'AB XLASB Stabber',
            fitContext: 'AB XLASB Stabber plex protector — never MWD-scram this hull.',
            entries: [
                { opponent: 'Pulse Maller', load: 'Hail', verdict: 'favoured', advice: 'AB control, get under lasers when you want it.' },
                { opponent: 'Beam Omen', load: 'Hail', verdict: 'even', advice: 'T1 trade. Tracking helps you under guns.' },
                { opponent: 'XLASB HAM Bellicose', load: 'Hail', verdict: 'even', advice: 'Flash-tank beacon fight.' },
                { opponent: 'Brawl Arbitrator', load: 'Hail', verdict: 'unfavoured', advice: 'Neuts and drones grind you. Leave if control sticks.' },
                { opponent: 'Neut Vexor', load: 'Hail', verdict: 'unfavoured', advice: 'Cap wall. Do not invent hero moments.' },
                { opponent: 'Dual Prop Scythe Fleet Issue', load: 'Hail', verdict: 'skill', advice: 'Stealable if you catch scram on their MWD fit.' },
                { opponent: 'Blaster Exequror Navy Issue', load: 'Hail', verdict: 'bail', advice: 'Navy brawler. Warp.' },
                { opponent: 'HAM Caracal Navy Issue', load: 'Hail', verdict: 'bail', advice: 'Do not invent Navy hero moments.' },
                { opponent: 'Polarized Augoror Navy Issue', load: 'Hail', verdict: 'bail', advice: 'Beacon brick deletes you.' },
            ],
        },
        {
            title: 'Vulcan Stabber',
            fitContext: 'MWD long-point Vulcan kite with twin LSE and twin RLML.',
            entries: [
                { opponent: 'AB XLASB Stabber', load: 'Barrage', verdict: 'even', advice: 'Sister hull — stay at range, defend the plex.' },
                { opponent: 'XLASB HAM Bellicose', load: 'Barrage', verdict: 'favoured', advice: 'Half-kite should own a committed flash tank if they misrange.' },
                { opponent: 'Long Point Arbitrator', load: 'Barrage', verdict: 'skill', advice: 'Point-range contest. Drones versus Vulcans.' },
                { opponent: 'Kite Omen Navy Issue', load: 'Barrage', verdict: 'unfavoured', advice: 'Navy mid-band. Die for the kill only when you choose to.' },
                { opponent: 'Blaster Exequror Navy Issue', load: 'Barrage', verdict: 'bail', advice: 'They catch you. Warp.' },
                { opponent: 'Armor RLML Scythe Fleet Issue', load: 'Barrage', verdict: 'unfavoured', advice: 'Low-commit catcher. Leave early.' },
                { opponent: 'RHML Osprey Navy Issue', load: 'Barrage', verdict: 'unfavoured', advice: 'Fatter kite with XLASB. Decline fair trades.' },
            ],
        },
    ],
}

export const stabberfiGuide: ShipGuide = {
    id: 'stabberfi',
    name: 'Stabber Fleet Issue',
    shortName: 'StabberFI',
    faction: 'Minmatar',
    shipId: 17713,
    tagline: 'Fairly weak, still useful: dual-prop plate for range control.',
    bonuses: [
        { label: 'Medium Projectile Turret damage', value: '5%' },
        { label: 'Medium Projectile Turret tracking', value: '7.5%' },
        { label: 'Medium Projectile Turret falloff', value: '7.5%' },
    ],
    roleBonus: 'Fleet Issue combat hull with projectile damage, tracking, and falloff',
    sections: [
        {
            id: 'overview',
            title: 'Overview',
            paragraphs: [
                'The hull has problems and sits mid on pure charts. Fly it anyway for Minmatar Fleet identity and for tools Scythe Fleet Issue lacks — especially a web and better guaranteed-brawl presence. Speed tank under guns; do not expect to beat a serious VNI in a held scramble.',
            ],
        },
        {
            id: 'dual-prop-plate',
            title: 'Dual Prop Stabber Fleet Issue',
            paragraphs: [
                'Dual prop, sixteen-hundred plate, autocannons. Strong against laser boats if you get on top; can punch up into some battlecruisers. Prefer this over Scythe Fleet when the fight is a guaranteed brawl or a smaller gang.',
            ],
        },
    ],
    matchups: [
        {
            title: 'Dual Prop Stabber Fleet Issue',
            fitContext: 'MWD + AB 1600 plate Vulcan for range control and punching up.',
            entries: [
                { opponent: 'Polarized Augoror Navy Issue', load: 'Hail', verdict: 'favoured', advice: 'Get under guns; speed tank the projectiles back.' },
                { opponent: 'Kite Omen Navy Issue', load: 'Hail', verdict: 'favoured', advice: 'Close laser kiters. Prefer guaranteed brawl over Scythe Fleet chasing.' },
                { opponent: 'Pulse Augoror Navy Issue', load: 'Hail', verdict: 'favoured', advice: 'Same — get on top.' },
                { opponent: 'Pulse Maller', load: 'Hail', verdict: 'favoured', advice: 'Laser boat under Vulcans.' },
                { opponent: 'Beam Omen', load: 'Hail', verdict: 'favoured', advice: 'T1 laser brick — scrub them.' },
                { opponent: '2X Neut HAM Osprey Navy Issue', load: 'Hail', verdict: 'skill', advice: 'Winnable. Watch neuts.' },
                { opponent: 'HAM Caracal Navy Issue', load: 'Hail', verdict: 'skill', advice: 'Tough buffer race.' },
                { opponent: 'Brawl Arbitrator', load: 'Hail', verdict: 'favoured', advice: 'Guaranteed-brawl presence is why you flew this over Scythe.' },
                { opponent: 'Dual Prop Scythe Fleet Issue', load: 'Hail', verdict: 'favoured', advice: 'You are the harder dedicated brawl.' },
                { opponent: 'Dual Rep Vexor Navy Issue', load: 'Hail', verdict: 'bail', advice: 'Do not take the straight brawl.' },
                { opponent: 'Blaster Exequror Navy Issue', load: 'Hail', verdict: 'unfavoured', advice: 'You cannot speed tank their apply. Leave.' },
            ],
        },
    ],
}

export const shipGuides: ShipGuide[] = [
    // T1 cruisers
    arbitratorGuide,
    mallerGuide,
    omenGuide,
    vexorGuide,
    bellicoseGuide,
    stabberGuide,
    // Navy cruisers (includes Fleet Issue)
    augniGuide,
    omenniGuide,
    caracalniGuide,
    ospreyniGuide,
    eniGuide,
    vniGuide,
    scythefiGuide,
    stabberfiGuide,
]
