import type { FleetRoleGuide } from './types'

const ACADEMY = 'https://www.eveonline.com/eve-academy/ships/combat-mechanics'
const ECM_SIM = 'https://eve-cs.com/scenarios/basics/ecm'

export const electronic_warfare: FleetRoleGuide = {
    slug: 'electronic-warfare',
    guide_slug: 'electronic-warfare-guide',
    name: 'Electronic Warfare',
    short_name: 'EWAR',
    lede: 'Stop the enemy doing their job. Jam their logistics and slow their locks.',
    tagline: 'Jam their locks.',
    capabilities: ['Electronic Warfare', 'Support'],
    hero_type_id: 640,
    read_minutes: 12,
    why: [
        'A ship that can’t lock can’t shoot, repair or point. ECM takes that away for twenty seconds at a time.',
        'Jam their logistics and the repairs stop. Jam their tackle and our fleet can leave. Damps never fail a roll: they slow locks and cut lock range.',
        'The enemy will try to kill you first. Knowing your range and when to move is half the role.',
    ],
    why_video: { youtube_id: 'mJJffgoSOQg', title: 'What the pod is... ECM?! Complete guide to ECM modules', source: 'Gildii Auscent · 2024' },
    ladder: [],
    ships_from_doctrines: 'listed',
    // Griffin, Kitsune, Scorpion, Tengu.
    ships_only: [584, 11194, 640, 29984],
    ship_jobs: {
        584: 'Cheap jams, easy to replace',
        11194: 'Fast and much stronger jams',
        640: 'Jams on a battleship tank',
        29984: 'ECM on a strategic cruiser',
    },
    lessons: [
        {
            id: 'ecm',
            title: 'ECM',
            summary: 'What a jam does, and how to make it land.',
            format: 'video',
            clips: [
                { src: 'https://videos.ctfassets.net/7lhcm73ukv5p/HDZzm1MWu4kp9PN99ZOmU/aa02693017b145bfb24b5c9276d8930b/0083_08_Ecm_Edit_02-01-8.webm', title: 'ECM', source: 'EVE Academy · CCP Games', url: `${ACADEMY}#ecm` },
            ],
            practice: { kind: 'sim', title: 'ECM', source: 'EVE Combat Sim', why: 'Fly it in your browser: jam the enemy and watch their locks drop.', url: ECM_SIM },
            body: [
                'A jam drops every lock the target has, and it can’t lock anything new for twenty seconds. It can still lock you.',
                'Each cycle is a dice roll: your jammer’s strength against their sensor strength. A racial jammer is strongest against one race’s sensors. A multispectral jammer works on every race, but weaker.',
            ],
            steps: [
                'Before the fight, paste a d-scan into our <a href="/dscan/">d-scan tool</a> and load jammers for the enemy’s race.',
                'Jam the target the FC gives you, and say which ship you have.',
                'Spread out. One jammer on each logi stops more repairs than three on one.',
            ],
        },
        {
            id: 'ewar-modules',
            title: 'Your EWAR modules',
            summary: 'ECM, burst jammers and damps: what each does in a fight.',
            format: 'read',
            body: [
                'Pick a module below to see what it does.',
            ],
            modules: [
                {
                    type_id: 2575, name: 'ECM', short: 'ECM', example: 'Radar ECM II',
                    impacts: [
                        { title: 'Break every lock', detail: 'A successful jam drops all of its locks for twenty seconds.' },
                        { title: 'Stop their repairs', detail: 'A jammed logistics ship can’t lock anyone, so it can’t repair anyone.' },
                        { title: 'Match their race', detail: 'Racial jammers are strongest against one sensor type. Check the enemy doctrine first.' },
                    ],
                    learn: { title: 'Watch on EVE Academy', url: `${ACADEMY}#ecm` },
                    practice: { title: 'Practice in EVE Combat Sim', url: ECM_SIM },
                },
                {
                    type_id: 2117, name: 'Burst jammer', short: 'Burst', example: 'Burst Jammer II',
                    impacts: [
                        { title: 'Breaks locks around you', detail: 'Every ship close to you, friend or enemy, loses its current locks.' },
                        { title: 'They lock again at once', detail: 'It buys a few seconds, not twenty. Time it to free a tackled ship.' },
                        { title: 'Not for logi', detail: 'Use your jammers on their logi. The burst is for tackle up close.' },
                    ],
                },
                {
                    type_id: 1969, name: 'Sensor dampener', short: 'Damp', example: 'Remote Sensor Dampener II',
                    impacts: [
                        { title: 'Snipers lose their locks', detail: 'With the range script, it can’t lock anything as far away as we are.' },
                        { title: 'Slow their locks', detail: 'With the resolution script, every lock takes longer, so they switch targets late.' },
                        { title: 'Slow their logistics', detail: 'A damped logistics ship locks slowly, so its repairs land late.' },
                    ],
                    learn: { title: 'Watch on EVE Academy', url: `${ACADEMY}#sensor-dampening` },
                },
            ],
        },
        {
            id: 'who-to-ewar',
            title: 'Who to target',
            summary: 'The ships that hurt most when they can’t do their job.',
            format: 'read',
            body: [
                'The FC picks EWAR targets. These are the usual ones.',
            ],
            lists: [
                {
                    title: 'Target first',
                    items: [
                        '<strong>Logistics.</strong> Jam or damp them and their repairs stop or land late.',
                        '<strong>Tackle,</strong> when the fleet needs to leave. A jammed ship can’t hold its point.',
                        '<strong>Snipers,</strong> with damps, so they can’t lock us from range.',
                    ],
                },
                {
                    title: 'Common problems',
                    items: [
                        '<strong>Everyone on one target:</strong> spread jammers across their logi.',
                        '<strong>The wrong racial jammer:</strong> it lands far less often. Check the enemy doctrine first.',
                        '<strong>Too far away:</strong> past optimal range, your modules get weaker fast.',
                    ],
                },
            ],
        },
        {
            id: 'staying-alive',
            title: 'Staying alive',
            summary: 'Range, speed, and why the enemy shoots EWAR first.',
            format: 'video',
            video: { youtube_id: 'UdHsobtlGvw', title: 'Newbie PVP EWAR 101', source: 'Nater Ormand · The Brave Dojo · 2023' },
            body: [
                'EWAR hurts the enemy, so they will try to kill you first. A jammed ship can always lock the ship jamming it.',
            ],
            steps: [
                'Sit near the edge of your optimal range, not on top of the target.',
                'Keep moving. A ship sitting still at zero is a killmail.',
                'If the enemy calls you primary, broadcast for reps and stay on the anchor.',
            ],
        },
    ],
    mistakes: [
        { title: 'Everyone on one Guardian', fix: 'One jammer each on three logi stops more repairs than three on one.' },
        { title: 'The wrong racial jammer', fix: 'It lands far less often. Check the enemy doctrine first.' },
        { title: 'Sitting still at zero', fix: 'Every ship you jam can still lock you. Keep range, keep moving.' },
        { title: 'Using the burst on logi', fix: 'They lock again at once. Use your jammers on logi, the burst on tackle.' },
    ],
    drills: [
        { id: 'ecm-sim', title: 'Fly ECM', how: 'In EVE Combat Sim: jam the enemy and watch their locks drop.', kind: 'setup' },
        { id: 'fleet-ewar', title: 'Fly EWAR on a fleet', how: 'Fly a ship from Ships for this role and work the targets the FC calls.', kind: 'fleet' },
    ],
    resources: [
        { kind: 'guide', title: 'D-scan tool', source: 'Minmatar Fleet', why: 'See the enemy hulls, and so their sensor types, before you load jammers.', url: '/dscan/' },
        { kind: 'video', title: 'What the pod is... ECM?! Complete guide to ECM modules', source: 'Gildii Auscent · 2024', why: 'Every ECM module and how jam chance works.', url: 'https://www.youtube.com/watch?v=mJJffgoSOQg' },
        { kind: 'video', title: 'Newbie PVP EWAR 101', source: 'Nater Ormand · The Brave Dojo · 2023', why: 'Every kind of electronic warfare, for a first fleet.', url: 'https://www.youtube.com/watch?v=UdHsobtlGvw' },
        { kind: 'ccp', title: 'Combat mechanics', source: 'EVE Academy · CCP Games', why: 'CCP’s short clips on ECM and sensor dampening.', url: `${ACADEMY}#ecm` },
        { kind: 'wiki', title: 'Electronic Countermeasures', source: 'EVE University wiki', why: 'The jam formula, bursts, and locking the jammer.', url: 'https://wiki.eveuniversity.org/Electronic_Countermeasures' },
        { kind: 'sim', title: 'ECM', source: 'EVE Combat Sim', why: 'Jam a target in your browser.', url: ECM_SIM },
    ],
}
