import type { FleetRoleGuide } from './types'

const DRAG_SIM = 'https://eve-cs.com/scenarios/movement/drag-bubbles'

export const fleet_disruption: FleetRoleGuide = {
    slug: 'fleet-disruption',
    guide_slug: 'fleet-disruption-guide',
    name: 'Fleet Disruption',
    short_name: 'Disruption',
    lede: 'Break up the enemy fleet. Lock down their anchor, boosh their logi away, bubble their exits and burn their drones and missiles.',
    tagline: 'Break their fleet apart.',
    capabilities: ['Tackle'],
    hero_type_id: 37480,
    read_minutes: 12,
    why: [
        'A fleet works because its ships are together: logi in range of the guns, everyone on the anchor. Disruption pulls it apart.',
        'Lock down their anchor and the fleet can’t leave. Boosh their logi off their battleships and the repairs stop. Burn their drones and missiles before they land.',
        'None of it shows up as damage, but it often decides who wins.',
    ],
    why_video: { youtube_id: 'ynAhyO2_BJ0', title: 'How to Control a Grid in EVE', source: 'Zip Slings · 2021' },
    ladder: [],
    ships_from_doctrines: 'listed',
    // Stabber Fleet Issue, Bifrost, Heretic, Nestor.
    ships_only: [17713, 37480, 22452, 33472],
    ship_jobs: {
        17713: 'Anchor tackle',
        37480: 'Booshing',
        22452: 'Bubbles',
        33472: 'Firewalls',
    },
    lessons: [
        {
            id: 'booshing',
            title: 'Booshing',
            summary: 'Everything within {mjfg_radius_km} km jumps with you. Use it on purpose.',
            format: 'diagram',
            diagrams: ['boosh-logi'],
            body: [
                'A command destroyer’s micro jump field generator jumps it, and up to {mjfg_max_ships} ships within {mjfg_radius_km} km, {mjfg_distance_km} km in the direction it is facing. Friends go too. A scrammed ship stays behind.',
            ],
            lists: [
                {
                    title: 'Bifrost',
                    type_id: 37480,
                    items: [
                        'Boosh their logi away from the ships they repair, on the FC’s call.',
                        'Before you press it, check who is within {mjfg_radius_km} km and which way you face.',
                        'In low-sec, booshing a neutral gives you a criminal timer, and you can’t jump or dock for 60 seconds after.',
                    ],
                },
            ],
            links: [
                { kind: 'wiki', title: 'Micro Jump Field Generator', source: 'EVE University wiki', why: 'How booshing works and what stops it.', url: 'https://wiki.eveuniversity.org/Propulsion_equipment#Micro_Jump_Field_Generator' },
            ],
        },
        {
            id: 'bubbles',
            title: 'Bubbles',
            summary: 'Where they work, and drag versus stop bubbles.',
            format: 'video',
            video: { youtube_id: 'Zmf9LuFTNsM', title: 'Interdictors and Bubbles 101', source: 'Stath Vaille · The Brave Dojo · 2019' },
            practice: { kind: 'sim', title: 'Drag Bubbles', source: 'EVE Combat Sim', why: 'Fly through a bubble camp in your browser and see how drag bubbles catch you.', url: DRAG_SIM },
            body: [
                'Bubbles work in null-sec, wormholes and low-sec at corruption level 5, not in the rest of the warzone. A ship in warp stops at the edge of the first bubble on its path.',
                'A <strong>stop bubble</strong> sits on a gate and catches traffic from every direction. A <strong>drag bubble</strong> sits on the warp line, so ships land far from the gate and have to burn back.',
            ],
            lists: [
                {
                    title: 'Heretic',
                    type_id: 22452,
                    items: [
                        'Launch where the FC calls, then burn out. Bubbles stop you warping too.',
                        'Check where our fleet will warp out before you launch. Don’t bubble our own exit.',
                    ],
                },
            ],
        },
        {
            id: 'firewalls',
            title: 'Firewalls',
            summary: 'Smartbombs that burn enemy drones and missiles before they land.',
            format: 'read',
            body: [
                'A smartbomb hits everything around the ship that fires it. A firewall uses that on purpose: it sits between our fleet and theirs, and burns their drones and missiles on the way in.',
            ],
            lists: [
                {
                    title: 'Nestor',
                    type_id: 33472,
                    items: [
                        'Sit where the FC puts you, between the fleets.',
                        'Smartbombs hit friends too. Keep away from our drones and tackle.',
                        'Expect to be primaried. Broadcast early and stay where the logi can reach you.',
                    ],
                },
            ],
            links: [
                { kind: 'wiki', title: 'Smartbombs', source: 'EVE University wiki', why: 'Range, damage and what a smartbomb hits.', url: 'https://wiki.eveuniversity.org/Smartbombs' },
            ],
        },
        {
            id: 'tackling-the-anchor',
            title: 'Tackling the anchor',
            summary: 'Lock down the enemy anchor so their fleet can’t leave or move together.',
            format: 'video',
            clips: [
                { src: 'https://videos.ctfassets.net/7lhcm73ukv5p/1ogOubZcuL61V0hKO9BOWI/38c9e43b4023b2a42abf76f92a1491f0/0083_06_Spiral_Tackle_En_1.webm', title: 'Spiral tackle', source: 'EVE Academy · CCP Games', url: 'https://www.eveonline.com/eve-academy/ships/combat-mechanics#spiral-tackle' },
            ],
            practice: { kind: 'sim', title: 'Spiral Approach', source: 'EVE Combat Sim', why: 'Fly it in your browser: spiral in and get tackle without being hit.', url: 'https://eve-cs.com/scenarios/movement/spiral-approach' },
            body: [
                'The enemy fleet follows its anchor. Hold the anchor and the whole fleet stays where we want it: it can’t warp off together or burn away from our guns.',
            ],
            lists: [
                {
                    title: 'Stabber Fleet Issue',
                    type_id: 17713,
                    items: [
                        'Burn to the anchor as soon as the FC calls it. Spiral in so their guns can’t track you.',
                        'Point it, then web it. A scram also stops its microwarpdrive and micro jump drive.',
                        'If a point won’t hold it, bump it off its align so it can’t warp.',
                        'Call it the moment you land tackle: your ship and the anchor’s name.',
                    ],
                },
                {
                    title: 'Common problems',
                    items: [
                        '<strong>Their fleet turns on you:</strong> broadcast for reps early and keep moving.',
                        '<strong>The anchor changes:</strong> the enemy picks a new anchor. Move to it on the FC’s call.',
                    ],
                },
            ],
            links: [
                { kind: 'wiki', title: 'Bumping', source: 'EVE University wiki', why: 'Mass, speed and angle, with examples.', url: 'https://wiki.eveuniversity.org/Bumping' },
            ],
        },
    ],
    mistakes: [
        { title: 'Booshing without looking', fix: 'Every ship within {mjfg_radius_km} km jumps with you, friends included. Check before you press it.' },
        { title: 'Bubbling our own exit', fix: 'A bubble on our warp-out catches us, not them. Check where the fleet aligns first.' },
        { title: 'Sitting in your own bubble', fix: 'You can’t warp out of it either. Launch, then burn clear.' },
        { title: 'Smartbombing our own drones', fix: 'Smartbombs hit everything around you. Keep clear of our drones and tackle.' },
    ],
    drills: [
        { id: 'spiral-sim', title: 'Fly Spiral Approach', how: 'In EVE Combat Sim: spiral in and get tackle without being hit.', kind: 'setup' },
        { id: 'drag-bubbles-sim', title: 'Fly Drag Bubbles', how: 'In EVE Combat Sim: get through a bubble camp to the gate.', kind: 'setup' },
        { id: 'fleet-disrupt', title: 'Fly disruption on a fleet', how: 'Fly a ship from Ships for this role and work the FC’s calls.', kind: 'fleet' },
    ],
    resources: [
        { kind: 'guide', title: 'Faction Warfare Battlefields', source: 'Minmatar Fleet', why: 'How battlefields work, and where our fleets fight on them.', url: '/learning/guides/faction-warfare-battlefields/' },
        { kind: 'video', title: 'Interdictors and Bubbles 101', source: 'Stath Vaille · The Brave Dojo · 2019', why: 'A full class on dictor flying: launching, placement, staying alive.', url: 'https://www.youtube.com/watch?v=Zmf9LuFTNsM' },
        { kind: 'video', title: 'How to Control a Grid in EVE', source: 'Zip Slings · 2021', why: 'Tackle, range and grid control as one skill.', url: 'https://www.youtube.com/watch?v=ynAhyO2_BJ0' },
        { kind: 'wiki', title: 'Interdictors', source: 'EVE University wiki', why: 'Drag and stop bubbles drawn out.', url: 'https://wiki.eveuniversity.org/Interdictors' },
        { kind: 'wiki', title: 'Bumping', source: 'EVE University wiki', why: 'Mass, speed and angle, with examples.', url: 'https://wiki.eveuniversity.org/Bumping' },
        { kind: 'sim', title: 'Drag Bubbles', source: 'EVE Combat Sim', why: 'Get through a bubble camp in your browser.', url: DRAG_SIM },
    ],
}
