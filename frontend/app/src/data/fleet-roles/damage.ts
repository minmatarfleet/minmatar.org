import type { FleetRoleGuide } from './types'

export const damage: FleetRoleGuide = {
    slug: 'damage',
    guide_slug: 'damage-guide',
    name: 'Damage',
    short_name: 'Damage',
    lede: 'Shoot what the FC calls, as fast as you can, and use your spare slots to help the fleet while you do.',
    tagline: 'Kill the primary, fast.',
    capabilities: ['DPS'],
    hero_type_id: 17732,
    read_minutes: 20,
    why: [
        'Damage wins fights. The faster we kill the primary, the less time their logistics have to repair it.',
        'Splitting damage slows everyone down. If our shots are spread across several ships, their logistics start repairing the next target before it is even called. Shoot the broadcast, lock the next target early, and load the right ammo for the range.',
        'Every pilot starts here, and these habits carry into every other role.',
    ],
    why_video: { youtube_id: 'JVwkmvLau70', title: 'Understanding Damage Application', source: 'Shizuka’s Station · 2021' },
    ladder: [],
    ships_from_doctrines: 'damage',
    // Typhoon, Tempest Fleet Issue, Apocalypse Navy Issue.
    ships_only: [644, 17732, 17726],
    lessons: [
        {
            id: 'anchor-up',
            title: 'Anchoring',
            summary: 'Stay on one pilot so reps reach you and the fleet shoots together.',
            format: 'diagram',
            diagrams: ['fleet-snake'],
            body: [
                'Everyone stays on one pilot, the anchor, so the fleet moves as one group. That keeps you in range of our logistics and defensive bubbles, and puts all our guns on the same target.',
                'The FC often anchors, but it works better when someone else does.',
            ],
            lists: [
                {
                    title: 'Important',
                    items: [
                        'Turret ships: <strong>keep at range 500–2,500 m</strong> on the anchor.',
                        'Missile ships: <strong>orbit the anchor at 500–2,500 m</strong>, unless we are kiting.',
                        '<strong>Always run your afterburner.</strong> Microwarpdrive only when the FC says so.',
                    ],
                },
                {
                    title: 'Common problems',
                    items: [
                        '<strong>Fleet snakes:</strong> if you are at the back, heat or pulse your prop mod to catch up.',
                        '<strong>Bumping</strong> throws off your tracking. Re-anchor and keep shooting.',
                        '<strong>The anchor gets tackled:</strong> break anchor when the FC calls it.',
                        '<strong>A smartbomber sits on the anchor:</strong> spread out when the FC calls it.',
                    ],
                },
            ],
            links: [
                { kind: 'sim', title: 'Fleet Basics: DPS', source: 'EVE Combat Sim', why: 'Anchor up and follow the broadcasts in a fleet fight in your browser.', url: 'https://eve-cs.com/scenarios/fleet-command/fleet-basics-dps' },
            ],
        },
        {
            id: 'target-calling',
            title: 'Target calling and focus fire',
            summary: 'Shoot the broadcast, lock the next target early, and switch when the FC calls it.',
            format: 'video',
            practice: { kind: 'sim', title: 'Fleet Basics: DPS', source: 'EVE Combat Sim', why: 'Fly it in your browser: anchor up, follow the target broadcasts, lock ahead and switch on the call.', url: 'https://eve-cs.com/scenarios/fleet-command/fleet-basics-dps' },
            video: { youtube_id: 'NlWlLgU9k8w', title: 'Hotkeys: all the broadcasts', source: 'Fua Consternation · 2021' },
            body: [
                'Enemy logistics can keep up with damage that is spread around, but not with a whole fleet on one ship. Shoot the primary, lock the next target early, and switch as soon as the FC calls it.',
            ],
            steps: [
                'Lock targets in the order they are broadcast.',
                'Shoot the primary, and <strong>only</strong> the primary.',
                'Put your neutralizers on the primary and secondary, unless the FC says otherwise.',
                'Watch your drones. Don’t send them into smartbombs.',
            ],
        },
        {
            id: 'broadcasting-for-repairs',
            title: 'Broadcasting for repairs',
            summary: 'When to ask for reps, and when not to.',
            format: 'video',
            video: { youtube_id: 'sP-iIc6nn5k', title: 'How to die in EVE Online', source: 'Minmatar Fleet training video' },
            body: [
                'Logistics repair whoever broadcasts. Broadcast early, once, and only for damage they can actually fix.',
            ],
            steps: [
                'Bind <strong>Need Armor</strong> (or <strong>Need Shield</strong>) to a key before you undock.',
                'Broadcast as soon as it’s clear you will be a target. Don’t wait until you are in structure.',
                'Broadcast once, and stay on the anchor so logistics can reach you.',
            ],
            donts: [
                '<strong>Don’t broadcast for bomb or smartbomb damage.</strong> It hits everyone at once and is over before reps can land, and all those broadcasts hide the pilot who really needs help.',
                'Don’t spam the broadcast.',
            ],
            links: [
                { kind: 'video', title: 'Hotkeys: all the broadcasts', source: 'Fua Consternation · 2021', why: 'Every fleet broadcast, including Need Armor and Need Shield, and how to bind them.', url: 'https://www.youtube.com/watch?v=NlWlLgU9k8w' },
                { kind: 'wiki', title: 'Logistics', source: 'EVE University wiki', why: 'How logistics locks and repairs, from their side of the broadcast.', url: 'https://wiki.eveuniversity.org/Logistics' },
            ],
        },
        {
            id: 'turrets',
            title: 'Turrets: range and tracking',
            summary: 'Why distance and speed make your guns miss.',
            format: 'video',
            clips: [
                { src: 'https://videos.ctfassets.net/7lhcm73ukv5p/7E4L8PIVJwgWrp3Es5lwGE/785621870f399bf170531a4781a18503/0083_01_Optimal_Range_Edit_03-01-1.webm', title: 'Optimal range', source: 'EVE Academy · CCP Games', url: 'https://www.eveonline.com/eve-academy/ships/combat-mechanics#optimal-range' },
                { src: 'https://videos.ctfassets.net/7lhcm73ukv5p/3RhZZxx4qgQlJqOQ59qXWe/93a397e729749f99df69e11c4926dd98/0083_03_Tracking_Edit_03-01-3.webm', title: 'Tracking', source: 'EVE Academy · CCP Games', url: 'https://www.eveonline.com/eve-academy/ships/combat-mechanics#tracking' },
            ],
            body: [
                'Your fitting window shows damage against a big, slow target at perfect range. Real targets are smaller, faster and further away. Turrets hit less the further a target is past optimal range, and the faster it moves across your screen.',
            ],
            steps: [
                'Hover over a gun to see its optimal range and falloff with the ammo you have loaded.',
                'Load ammo that keeps the primary inside optimal plus half your falloff at the FC’s range.',
                'If a fast ship is close, don’t fly toward it. That makes it harder to hit. Web it instead.',
            ],
            links: [
                { kind: 'sim', title: 'Turret Range', source: 'EVE Combat Sim', why: 'Targets at different ranges: watch optimal and falloff decide what lands.', url: 'https://eve-cs.com/scenarios/basics/turret-range' },
                { kind: 'sim', title: 'Turret Tracking: Transversal', source: 'EVE Combat Sim', why: 'Two targets orbit you: see how sideways speed makes your turrets miss.', url: 'https://eve-cs.com/scenarios/basics/turret-tracking-transversal' },
                { kind: 'wiki', title: 'Turret mechanics', source: 'EVE University wiki', why: 'The hit-chance formula, with worked examples.', url: 'https://wiki.eveuniversity.org/Turret_mechanics' },
            ],
        },
        {
            id: 'missiles',
            title: 'Missiles: signature and speed',
            summary: 'Why small, fast ships take less missile damage.',
            format: 'video',
            clips: [
                { src: 'https://videos.ctfassets.net/7lhcm73ukv5p/6aYFx1uV3XdAQtPbaZlJAK/3f0d574003cf2f03ed0fc6a6183ca5e8/0083_02_Missile_Range_Edit_04-02-1.webm', title: 'Missile range', source: 'EVE Academy · CCP Games', url: 'https://www.eveonline.com/eve-academy/ships/combat-mechanics#missile-range' },
                { src: 'https://videos.ctfassets.net/7lhcm73ukv5p/10J6ZVfJmv6utzQry9NvE3/f89b1dc37c3734791291610a991b8f96/0083_04_Missile_Application_Edit_03-01-4.webm', title: 'Missile application', source: 'EVE Academy · CCP Games', url: 'https://www.eveonline.com/eve-academy/ships/combat-mechanics#missile-application' },
            ],
            body: [
                'Missiles never miss, but small ships only take part of the explosion, and fast ships take even less.',
                'Missiles also take time to fly, so after a switch your first volley lands a few seconds late.',
            ],
            steps: [
                'Fire as soon as the FC calls a target. Your missiles already land later than turret shots.',
                'Painters and webs make every missile in the fleet hit harder. Use yours on the primary when the FC asks.',
            ],
            links: [
                { kind: 'sim', title: 'Missile Range', source: 'EVE Combat Sim', why: 'Targets at different ranges and speeds: watch flight range and application.', url: 'https://eve-cs.com/scenarios/basics/missile-range' },
                { kind: 'sim', title: 'Missile Range Advanced', source: 'EVE Combat Sim', why: 'How your own ship’s speed stretches or shortens how far your missiles reach.', url: 'https://eve-cs.com/scenarios/basics/missile-range-advanced' },
                { kind: 'wiki', title: 'Missile mechanics', source: 'EVE University wiki', why: 'The damage formula, explosion radius and velocity, worked through.', url: 'https://wiki.eveuniversity.org/Missile_mechanics' },
            ],
        },
        {
            id: 'ammo',
            title: 'Ammo selection',
            summary: 'Which ammo to load, and why.',
            format: 'ammo',
            body: [
                'Carry every type of ammo the doctrine fit lists. Long-range ammo reaches further but hits softer. Short-range ammo hits harder, but only up close.',
                'The charts show the ammo our doctrine ships carry. Pick a ship under a chart to see how much damage lands on it.',
            ],
            steps: [
                'Load ammo for the FC’s range before the fight starts.',
                'Change ammo in a quiet moment. Reloading stops your guns for several seconds.',
                'If the FC calls a damage type, switch to ammo that deals it.',
            ],
            links: [
                { kind: 'wiki', title: 'Damage types', source: 'EVE University wiki', why: 'EM, thermal, kinetic and explosive, and which resists each hull is weak to.', url: 'https://wiki.eveuniversity.org/Damage_types' },
            ],
            ammo_notes: {
                projectile: 'Barrage reaches further. Hail and EMP hit harder up close.',
                laser: 'Scorch and Aurora reach further. Conflagration and Multifrequency hit hardest up close. Crystals swap with no reload.',
                hybrid: 'Null and Spike reach further. Void and Javelin hit harder up close.',
                torpedo: 'Rage hits hardest, but only on big, slow targets. Navy torpedoes fly a little further and do more to smaller ships.',
                heavy_assault_missile: 'Javelin reaches; Rage hits hardest up close.',
            },
        },
        {
            id: 'utility-slots',
            title: 'Utility slots',
            summary: 'Neuts, painters, webs and other modules that help the fleet while your guns keep shooting.',
            format: 'read',
            body: [
                'Most doctrine fits have a spare slot with something other than guns. Each module solves a different problem. Use them without taking your guns off the primary.',
                'Pick a module below to see what it does.',
            ],
            modules: [
                {
                    type_id: 12271, name: 'Energy neutralizer', short: 'Neut', example: 'Heavy Energy Neutralizer II',
                    impacts: [
                        { title: 'Turn off active hardeners', detail: 'Hardeners need capacitor. Drain it and their resists drop for the whole fleet.' },
                        { title: 'Disrupt lasers and hybrids', detail: 'Lasers and hybrid guns use capacitor to fire. Empty it and they stop shooting.' },
                        { title: 'Shut down key ships', detail: 'Smartbombing Nestors, webbing Vindicators, enemy neutralizers, and logistics that need capacitor to repair.' },
                    ],
                    learn: { title: 'Watch on EVE Academy', url: 'https://www.eveonline.com/eve-academy/ships/combat-mechanics#energy-neutralisers' },
                    practice: { title: 'Practice in EVE Combat Sim', url: 'https://eve-cs.com/scenarios/basics/neuts' },
                },
                {
                    type_id: 19806, name: 'Target painter', short: 'Painter', example: 'Target Painter II',
                    impacts: [
                        { title: 'Missiles land more', detail: 'A bigger target takes more of each explosion, so every missile in the fleet hits harder.' },
                        { title: 'Big guns hit small ships', detail: 'Battleship guns struggle against small ships. Painting a cruiser helps them hit.' },
                        { title: 'Faster locks for everyone', detail: 'Bigger targets lock faster, so the whole fleet locks a painted primary sooner.' },
                    ],
                    learn: { title: 'Watch on EVE Academy', url: 'https://www.eveonline.com/eve-academy/ships/combat-mechanics#target-painting' },
                    practice: { title: 'Practice in EVE Combat Sim', url: 'https://eve-cs.com/scenarios/basics/target-painters' },
                },
                {
                    type_id: 2109, name: 'Tracking disruptor', short: 'TD', example: 'Tracking Disruptor II',
                    impacts: [
                        { title: 'Cut a kiter’s range', detail: 'With the range script, an enemy turret ship’s range shrinks. It misses or has to come closer.' },
                        { title: 'Cut its tracking up close', detail: 'With the tracking script, a close-range ship can’t hit ships orbiting it.' },
                        { title: 'Turrets only', detail: 'It does nothing to missiles. Those need a guidance disruptor.' },
                    ],
                    learn: { title: 'Watch on EVE Academy', url: 'https://www.eveonline.com/eve-academy/ships/combat-mechanics#weapon-disruption' },
                },
                {
                    type_id: 1969, name: 'Sensor dampener', short: 'Damp', example: 'Remote Sensor Dampener II',
                    impacts: [
                        { title: 'Snipers lose their locks', detail: 'With the range script, it can’t lock anything as far away as we are.' },
                        { title: 'Slow their locks', detail: 'With the resolution script, every lock takes longer, so they switch targets late.' },
                        { title: 'Slow their logistics', detail: 'A damped logistics ship locks slowly, so its repairs land late.' },
                    ],
                    learn: { title: 'Watch on EVE Academy', url: 'https://www.eveonline.com/eve-academy/ships/combat-mechanics#sensor-dampening' },
                },
                {
                    type_id: 2567, name: 'ECM', short: 'ECM', example: 'Multispectral ECM II',
                    impacts: [
                        { title: 'Break every lock', detail: 'A successful jam drops all of its locks for one cycle.' },
                        { title: 'Stop their repairs', detail: 'A jammed logistics ship can’t lock anyone, so it can’t repair anyone.' },
                        { title: 'Chance, not certainty', detail: 'Each cycle is a dice roll. Racial jammers work best against the matching sensor type.' },
                    ],
                    learn: { title: 'Watch on EVE Academy', url: 'https://www.eveonline.com/eve-academy/ships/combat-mechanics#ecm' },
                    practice: { title: 'Practice in EVE Combat Sim', url: 'https://eve-cs.com/scenarios/basics/ecm' },
                },
                {
                    type_id: 527, name: 'Stasis webifier', short: 'Web', example: 'Stasis Webifier II',
                    impacts: [
                        { title: 'Guns track fast ships', detail: 'A slower target is easier for your turrets to hit.' },
                        { title: 'Missiles land more', detail: 'Missiles do less to fast targets. A webbed target takes more damage.' },
                        { title: 'Pin tackle in place', detail: 'A webbed frigate can’t orbit fast or burn out of range.' },
                    ],
                    practice: { title: 'Practice in EVE Combat Sim', url: 'https://eve-cs.com/scenarios/basics/webs' },
                },
                {
                    type_id: 3244, name: 'Warp disruptor', short: 'Point', example: 'Warp Disruptor II',
                    impacts: [
                        { title: 'Stop a warp', detail: 'A pointed ship can’t warp off while the point holds.' },
                        { title: 'Long point', detail: 'It reaches further than a scrambler, but it doesn’t turn off a microwarpdrive.' },
                        { title: 'Hold the kill', detail: 'Keep it on until the target dies or the FC calls it off.' },
                    ],
                    learn: { title: 'Watch on EVE Academy', url: 'https://www.eveonline.com/eve-academy/ships/combat-mechanics#warp-disruption' },
                },
            ],
            links: [
                { kind: 'wiki', title: 'Electronic warfare', source: 'EVE University wiki', why: 'Painters, disruptors, dampeners and ECM in depth.', url: 'https://wiki.eveuniversity.org/Electronic_warfare' },
                { kind: 'wiki', title: 'Capacitor warfare', source: 'EVE University wiki', why: 'Neutralizers and how capacitor runs out.', url: 'https://wiki.eveuniversity.org/Capacitor_warfare' },
                { kind: 'wiki', title: 'Warp disruption', source: 'EVE University wiki', why: 'Points, scrams and what stops a warp.', url: 'https://wiki.eveuniversity.org/Warp_disruption' },
            ],
        },
        {
            id: 'buffer-and-overheat',
            title: 'Buffer and overheat',
            summary: 'Overheat when it counts, without burning your modules out.',
            format: 'video',
            video: { youtube_id: '6HsJxe3pUzA', title: 'Overheating: an in-depth look', source: 'Fua Consternation · 2024' },
            body: [
                'Overheating makes a module stronger, but damages it. A burnt module stops working until it is repaired.',
                'Overheat when the FC calls it: guns on a primary that has to die now, or hardeners when you are being shot. Heat in short bursts.',
            ],
            steps: [
                'Group your guns in the fitting window so one button fires and heats them all.',
                'Shift-click a module to turn overheat on or off.',
                'Stop before a module burns out. Carry nanite repair paste to fix heat damage in space.',
            ],
            links: [
                { kind: 'wiki', title: 'Overheating', source: 'EVE University wiki', why: 'Which modules overheat, what heat does to the rack, and repairs.', url: 'https://wiki.eveuniversity.org/Overheating' },
            ],
        },
    ],
    mistakes: [
        { title: 'Leaving the anchor', fix: 'You fall out of logistics range and out of the fight. Stay on the anchor unless the FC says otherwise.' },
        { title: 'Broadcasting for bomb or smartbomb damage', fix: 'It hides the pilots who really need reps. Only broadcast for damage from guns and missiles.' },
        { title: 'Splitting damage', fix: 'Their logistics get time to repair the next target, and every kill takes longer. Shoot the broadcast.' },
        { title: 'The wrong ammo for the range', fix: 'Long-range ammo up close throws damage away. Change ammo before the range changes.' },
        { title: 'Overheating until it burns', fix: 'Burnt modules stop working. Heat in short bursts and stop early.' },
    ],
    drills: [
        { id: 'fleet-basics-sim', title: 'Fly Fleet Basics: DPS', how: 'In EVE Combat Sim: anchor up, follow the broadcasts and switch on the call.', kind: 'setup' },
        { id: 'fleet-lock-ahead', title: 'Lock ahead on a fleet', how: 'Have the next target locked when the switch is called, every time.', kind: 'fleet' },
        { id: 'setup-broadcasts', title: 'Set up broadcast hotkeys', how: 'Lock broadcast, align and warp to broadcast, on keys you can reach.', kind: 'setup' },
        { id: 'fleet-strategic', title: 'Fly a strategic op in a doctrine damage ship', how: 'Any hull from Ships we fly, in the doctrine the MOTD calls.', kind: 'fleet' },
    ],
    resources: [
        { kind: 'guide', title: 'New Player Fleet Guide', source: 'Minmatar Fleet', why: 'Broadcasts, the overview, and who to shoot when the fight starts.', url: '/learning/guides/new-player-fleet-guide/' },
        { kind: 'guide', title: 'Fleet Types and Your Hangar', source: 'Minmatar Fleet', why: 'Which doctrine hull to buy first, and which to skip.', url: '/learning/guides/onboarding-fleet-types-and-hangar/' },
        { kind: 'guide', title: 'Doctrines', source: 'Minmatar Fleet', why: 'Every current doctrine and its fits.', url: '/ships/doctrines/list/' },
        { kind: 'video', title: 'How to die in EVE Online', source: 'Minmatar Fleet training video', why: 'Our own training video: the mistakes that get pilots killed on our fleets.', url: 'https://www.youtube.com/watch?v=sP-iIc6nn5k' },
        { kind: 'video', title: 'Understanding Damage Application', source: 'Shizuka’s Station · 2021', why: 'Tracking, signature and explosion velocity, shown on screen.', url: 'https://www.youtube.com/watch?v=JVwkmvLau70' },
        { kind: 'video', title: 'Overheating: an in-depth look', source: 'Fua Consternation · 2024', why: 'What heat does, what it burns, and how to manage it.', url: 'https://www.youtube.com/watch?v=6HsJxe3pUzA' },
        { kind: 'wiki', title: 'Turret mechanics', source: 'EVE University wiki', why: 'The hit-chance formula, with worked examples.', url: 'https://wiki.eveuniversity.org/Turret_mechanics' },
        { kind: 'wiki', title: 'Missile mechanics', source: 'EVE University wiki', why: 'Explosion radius and velocity against signature and speed.', url: 'https://wiki.eveuniversity.org/Missile_mechanics' },
        { kind: 'sim', title: 'Fleet Basics: DPS', source: 'EVE Combat Sim', why: 'Anchor up and follow target broadcasts in a fleet fight.', url: 'https://eve-cs.com/scenarios/fleet-command/fleet-basics-dps' },
        { kind: 'sim', title: 'Turret Tracking: Transversal', source: 'EVE Combat Sim', why: 'See sideways speed make your turrets miss.', url: 'https://eve-cs.com/scenarios/basics/turret-tracking-transversal' },
        { kind: 'sim', title: 'Missile Range', source: 'EVE Combat Sim', why: 'Flight range and application against moving targets.', url: 'https://eve-cs.com/scenarios/basics/missile-range' },
        { kind: 'sim', title: 'Sandbox', source: 'EVE Combat Sim', why: 'Your own doctrine fit against respawning targets.', url: 'https://eve-cs.com/scenarios/sandbox/sandbox' },
    ],
}
