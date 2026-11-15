import type { FleetRoleGuide } from './types'

const ACADEMY = 'https://www.eveonline.com/eve-academy/ships/combat-mechanics'
const WEBS_SIM = 'https://eve-cs.com/scenarios/basics/webs'
const PAINTER_SIM = 'https://eve-cs.com/scenarios/basics/target-painters'
const SPIRAL_SIM = 'https://eve-cs.com/scenarios/movement/spiral-approach'

export const fleet_support: FleetRoleGuide = {
    slug: 'fleet-support',
    guide_slug: 'fleet-support-guide',
    name: 'Fleet Support',
    short_name: 'Support',
    lede: 'Hold the enemy in place and make every shot count. Webs, scrams, points and painters on the ships the FC calls.',
    tagline: 'Hold the enemy in place.',
    capabilities: ['Tackle', 'Recon'],
    hero_type_id: 12017,
    read_minutes: 12,
    why: [
        'A fight only happens when the enemy can’t leave. A point stops them warping, a scram stops their microwarpdrive, and a web stops them running.',
        'Webs and painters also make our guns and missiles hit harder. A slow, painted target takes more of every volley.',
        'Fleets are always short of support. One pilot holding the right ship changes what the FC can take.',
    ],
    why_video: { youtube_id: 'ynAhyO2_BJ0', title: 'How to Control a Grid in EVE', source: 'Zip Slings · 2021' },
    ladder: [],
    ships_from_doctrines: 'listed',
    // Devoter, Huginn, Loki, Barghest, Vindicator.
    ships_only: [12017, 11961, 29990, 33820, 17740],
    ship_jobs: {
        12017: 'Defensive bubbles and tackle',
        11961: 'Webs and painters',
        29990: 'Webs',
        33820: 'Scrams',
        17740: 'Webs',
    },
    lessons: [
        {
            id: 'holding-targets',
            title: 'Points and scrams',
            summary: 'Stop the ship the FC calls from leaving, and say that you have it.',
            format: 'video',
            clips: [
                { src: 'https://videos.ctfassets.net/7lhcm73ukv5p/1XMQgd1HRabd1IsJnB1eJi/986acfd2ce84d17e5d0f8657ec563eb7/0083_05_Warp_Disruption_Edit_03-01-5.webm', title: 'Warp disruption', source: 'EVE Academy · CCP Games', url: `${ACADEMY}#warp-disruption` },
                { src: 'https://videos.ctfassets.net/7lhcm73ukv5p/1ogOubZcuL61V0hKO9BOWI/38c9e43b4023b2a42abf76f92a1491f0/0083_06_Spiral_Tackle_En_1.webm', title: 'Spiral tackle', source: 'EVE Academy · CCP Games', url: `${ACADEMY}#spiral-tackle` },
            ],
            practice: { kind: 'sim', title: 'Spiral Approach', source: 'EVE Combat Sim', why: 'Fly it in your browser: spiral in and get tackle without being hit.', url: SPIRAL_SIM },
            body: [
                'A <strong>point</strong> reaches far and stops a ship warping. A <strong>scram</strong> reaches less far, but also turns off its microwarpdrive and micro jump drive.',
                'The enemy fleet follows its anchor. Hold the anchor and the fleet stays.',
            ],
            steps: [
                'Point the anchor or the ship the FC calls, before anything else.',
                'Call it the moment it lands: your ship and the name you hold.',
                'Hold it until the target dies or the FC says to drop it.',
            ],
        },
        {
            id: 'webs-and-painters',
            title: 'Webs and painters',
            summary: 'Slow targets can’t run, and they take more damage.',
            format: 'video',
            clips: [
                { src: 'https://videos.ctfassets.net/7lhcm73ukv5p/47KfE1MWBLpLAxclI86QyO/3d2467b60f285003db46b1c93f6060a9/0083_10_Target_Painting_Edit_02-01-10.webm', title: 'Target painting', source: 'EVE Academy · CCP Games', url: `${ACADEMY}#target-painting` },
            ],
            practice: { kind: 'sim', title: 'Webs', source: 'EVE Combat Sim', why: 'Web targets in your browser and watch them slow down.', url: WEBS_SIM },
            diagrams: ['paint-web-torpedoes'],
            body: [
                'A web slows the target, so it can’t run and our guns can track it. A painter makes it bigger, so missiles and big guns hit it harder and everyone locks it faster.',
            ],
            lists: [
                { title: 'Huginn', type_id: 11961, items: ['Long-range webs and painters: slow and paint the primary from outside their guns.'] },
                { title: 'Loki', type_id: 29990, items: ['Long-range webs on a tough hull: hold fast ships still for the fleet.'] },
                { title: 'Vindicator', type_id: 17740, items: ['The strongest webs in the fleet: stop a target almost dead in space.'] },
            ],
            links: [
                { kind: 'sim', title: 'Target Painters', source: 'EVE Combat Sim', why: 'See what a painter does to your damage.', url: PAINTER_SIM },
            ],
        },
        {
            id: 'heavy-tackle',
            title: 'Heavy tackle',
            summary: 'The Devoter and the Barghest: tackle that holds anything.',
            format: 'read',
            body: [
                'Some targets fight back hard or try to jump away. Heavy tackle holds them anyway.',
            ],
            lists: [
                {
                    title: 'Devoter',
                    type_id: 12017,
                    items: [
                        'With a focused script, its field generator is a point nothing can break. Warp core stabilisers don’t help, and the scramble script stops micro jump drives and boosh.',
                        'In null-sec, its bubble on our fleet makes ships warping in land at the edge, not on top of us.',
                        'With the bubble up it can’t be repaired. Turn it on when the FC calls it.',
                    ],
                },
                {
                    title: 'Barghest',
                    type_id: 33820,
                    items: [
                        'A battleship with long scrams: it holds a target and turns off its microwarpdrive from further out.',
                    ],
                },
            ],
        },
        {
            id: 'support-modules',
            title: 'Your support modules',
            summary: 'What each module does in a fight.',
            format: 'read',
            body: [
                'Pick a module below to see what it does.',
            ],
            modules: [
                {
                    type_id: 3244, name: 'Warp disruptor', short: 'Point', example: 'Warp Disruptor II',
                    impacts: [
                        { title: 'Stop a warp', detail: 'A pointed ship can’t warp off while the point holds.' },
                        { title: 'Long reach', detail: 'It reaches further than a scrambler, but it doesn’t turn off a microwarpdrive.' },
                        { title: 'Hold the kill', detail: 'Keep it on until the target dies or the FC calls it off.' },
                    ],
                    learn: { title: 'Watch on EVE Academy', url: `${ACADEMY}#warp-disruption` },
                },
                {
                    type_id: 448, name: 'Warp scrambler', short: 'Scram', example: 'Warp Scrambler II',
                    impacts: [
                        { title: 'Stop a warp', detail: 'It is twice as strong as a point, so it holds a ship with one warp core stabiliser.' },
                        { title: 'Turn off their microwarpdrive', detail: 'A scrammed ship crawls on its afterburner or nothing.' },
                        { title: 'No jumping away', detail: 'It stops micro jump drives, and a scrammed command destroyer can’t boosh.' },
                    ],
                    learn: { title: 'Watch on EVE Academy', url: `${ACADEMY}#warp-disruption` },
                },
                {
                    type_id: 527, name: 'Stasis webifier', short: 'Web', example: 'Stasis Webifier II',
                    impacts: [
                        { title: 'Guns track fast ships', detail: 'A slower target is easier for our turrets to hit.' },
                        { title: 'Missiles land more', detail: 'Missiles do less to fast targets. A webbed target takes more damage.' },
                        { title: 'Pin tackle in place', detail: 'A webbed frigate can’t orbit fast or burn out of range.' },
                    ],
                    practice: { title: 'Practice in EVE Combat Sim', url: WEBS_SIM },
                },
                {
                    type_id: 19806, name: 'Target painter', short: 'Painter', example: 'Target Painter II',
                    impacts: [
                        { title: 'Missiles land more', detail: 'A bigger target takes more of each explosion, so every missile in the fleet hits harder.' },
                        { title: 'Big guns hit small ships', detail: 'Battleship guns struggle against small ships. Painting a cruiser helps them hit.' },
                        { title: 'Faster locks for everyone', detail: 'Bigger targets lock faster, so the whole fleet locks a painted primary sooner.' },
                    ],
                    learn: { title: 'Watch on EVE Academy', url: `${ACADEMY}#target-painting` },
                    practice: { title: 'Practice in EVE Combat Sim', url: PAINTER_SIM },
                },
                {
                    type_id: 4248, name: 'Warp disruption field generator', short: 'HIC', example: 'Warp Disruption Field Generator II',
                    impacts: [
                        { title: 'A point nothing breaks', detail: 'With a focused script it holds one target, whatever stabilisers it fits.' },
                        { title: 'Stops booshing', detail: 'The scramble script stops the target’s micro jump drive and field generator.' },
                        { title: 'A bubble in null-sec', detail: 'Unscripted, it makes a bubble around the Devoter. It can’t be repaired while it’s up.' },
                    ],
                },
            ],
        },
    ],
    mistakes: [
        { title: 'Holding the wrong ship', fix: 'A point on something the fleet isn’t killing does nothing. Point the anchor or the call.' },
        { title: 'Not calling your tackle', fix: 'The FC plans the fight around what is held. Say your ship and the name the moment it lands.' },
        { title: 'Dropping point too early', fix: 'Hold it until the target dies or the FC says to drop it.' },
        { title: 'Bubbling with no reps coming', fix: 'A Devoter with its bubble up can’t be repaired. Turn it on when the FC calls it.' },
    ],
    drills: [
        { id: 'spiral-sim', title: 'Fly Spiral Approach', how: 'In EVE Combat Sim: spiral in and get tackle without being hit.', kind: 'setup' },
        { id: 'webs-sim', title: 'Fly Webs', how: 'In EVE Combat Sim: web targets and watch them slow down.', kind: 'setup' },
        { id: 'fleet-tackle', title: 'Hold the anchor on a fleet', how: 'Point the called target on a fleet and call it on comms.', kind: 'fleet' },
    ],
    resources: [
        { kind: 'guide', title: 'Faction Warfare Battlefields', source: 'Minmatar Fleet', why: 'Where tackle sits on a battlefield, and why not on our own landing.', url: '/learning/guides/faction-warfare-battlefields/' },
        { kind: 'video', title: 'How to Control a Grid in EVE', source: 'Zip Slings · 2021', why: 'Tackle, range and grid control as one skill.', url: 'https://www.youtube.com/watch?v=ynAhyO2_BJ0' },
        { kind: 'ccp', title: 'Warp disruption and spiral tackle', source: 'EVE Academy · CCP Games', why: 'CCP’s short clips on points, scrams and spiral tackle.', url: `${ACADEMY}#warp-disruption` },
        { kind: 'wiki', title: 'Warp disruption', source: 'EVE University wiki', why: 'Points, scrams, strength and stabilisers.', url: 'https://wiki.eveuniversity.org/Warp_disruption' },
        { kind: 'wiki', title: 'Heavy Interdiction Cruisers', source: 'EVE University wiki', why: 'The bubble, the focused scripts, and the four hulls.', url: 'https://wiki.eveuniversity.org/Heavy_Interdiction_Cruisers' },
        { kind: 'sim', title: 'Spiral Approach', source: 'EVE Combat Sim', why: 'Get tackle without being tracked.', url: SPIRAL_SIM },
    ],
}
