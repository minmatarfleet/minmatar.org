import type { FleetRoleGuide } from './types'

const NEUTS_SIM = 'https://eve-cs.com/scenarios/basics/neuts'
const NOS_SIM = 'https://eve-cs.com/scenarios/basics/nosferatu-nos'
const ACADEMY_NEUTS = 'https://www.eveonline.com/eve-academy/ships/combat-mechanics#energy-neutralisers'

export const capacitor_warfare: FleetRoleGuide = {
    slug: 'capacitor-warfare',
    guide_slug: 'capacitor-warfare-guide',
    name: 'Capacitor Warfare',
    short_name: 'Capacitor',
    lede: 'Drain the ships that matter. Repairs, hardeners, points and most guns stop when the capacitor runs out.',
    tagline: 'Drain the ships that matter.',
    capabilities: ['Capacitor Warfare', 'Support'],
    hero_type_id: 17920,
    read_minutes: 12,
    why: [
        'Almost everything a ship does in a fight uses capacitor. Drain it and their logistics stop repairing, their hardeners switch off, and their lasers stop firing.',
        'Damage has to get through a ship’s tank and the repairs on top of it. Neuts skip both: empty the logi and the enemy fleet only has its buffer left.',
        'You can start in a cheap Armageddon and work up to the Bhaalgorn, the ship enemy logi fear most.',
    ],
    why_video: { youtube_id: 'vYiUIvjVqrM', title: 'Newbee Tuesday: capacitor warfare', source: 'Imperium News · 2015' },
    ladder: [
        { rung: 1, ship_type_id: 643, name: 'Armageddon', hull_class: 'Battleship', job: 'Battleship neuts with bonused range, and drones.' },
        { rung: 2, ship_type_id: 17922, name: 'Ashimmu', hull_class: 'Cruiser', job: 'A fast neut and nos cruiser whose nos drains at any capacitor level.' },
        { rung: 2, ship_type_id: 20125, name: 'Curse', hull_class: 'Combat Recon Ship', job: 'Neuts from far out of their guns’ reach.' },
        { rung: 2, ship_type_id: 29986, name: 'Legion', hull_class: 'Strategic Cruiser', job: 'Neuts on a heavy tank, with the right subsystem.' },
        { rung: 3, ship_type_id: 17920, name: 'Bhaalgorn', hull_class: 'Battleship', job: 'The heaviest drain in the doctrine.' },
    ],
    lessons: [
        {
            id: 'neuts-and-nos',
            title: 'Neuts and nos',
            summary: 'What each one does, and why low capacitor falls fast.',
            format: 'video',
            clips: [
                { src: 'https://videos.ctfassets.net/7lhcm73ukv5p/272zt5MZZl8zVdI7JcdJf5/2c54b3070ceb8d5a1e0a82e28297d69f/Energy_Neutralisers_Updated-1.webm', title: 'Energy neutralisers', source: 'EVE Academy · CCP Games', url: ACADEMY_NEUTS },
            ],
            practice: { kind: 'sim', title: 'Energy Neutralizers', source: 'EVE Combat Sim', why: 'Fly it in your browser: empty a dual-rep Brutix’s capacitor before it kills your drones.', url: NEUTS_SIM },
            body: [
                'A <strong>neutralizer</strong> drains the target’s capacitor and costs you some of yours. A <strong>nosferatu</strong> takes capacitor from the target and gives it to you, but only while you have less than they do. Blood Raider ships, the Ashimmu and the Bhaalgorn, drain with nos whatever your capacitor.',
                'Capacitor recharges fastest at about a quarter full. Getting a ship there is the hard part. Below that, every cycle takes more than it gets back, and it empties fast.',
            ],
            steps: [
                'Neut the primary and secondary, unless the FC gives you a neut target.',
                'Start your neuts as soon as the target is in range, and keep them on until it is dry.',
                'Run your nos all the time. It keeps your own neuts going.',
            ],
            links: [
                { kind: 'sim', title: 'Nosferatu (Nos)', source: 'EVE Combat Sim', why: 'See when a nos drains and when it does nothing.', url: NOS_SIM },
            ],
        },
        {
            id: 'who-to-neut',
            title: 'Who to neut',
            summary: 'The ships that stop working when their capacitor runs out.',
            format: 'read',
            body: [
                'The FC picks neut targets by what each ship needs capacitor for. These are the usual ones.',
            ],
            lists: [
                {
                    title: 'Neut first',
                    items: [
                        '<strong>Logistics.</strong> Every repair costs capacitor. Drain one Guardian and its chain partner starts to starve too.',
                        '<strong>Key ships:</strong> smartbombing Nestors, webbing Vindicators, and enemy neut ships like Bhaalgorns.',
                        '<strong>Ships with active hardeners.</strong> Empty capacitor turns the hardeners off, and their resists drop for the whole fleet.',
                        '<strong>Laser and hybrid ships.</strong> Their guns use capacitor to fire.',
                    ],
                },
                {
                    title: 'Common problems',
                    items: [
                        '<strong>Everyone on one target:</strong> once a ship is dry, extra neuts on it are wasted. Move to the next one.',
                        '<strong>Target too far:</strong> two falloffs out, a neut drains almost nothing. Close in, or leave it to a longer-range ship.',
                    ],
                },
            ],
        },
        {
            id: 'neut-fit',
            title: 'Your neut fit',
            summary: 'The modules on our neut fits and what each one does in a fight.',
            format: 'read',
            body: [
                'Our neut fits use the same few modules. Pick one below to see what it does.',
            ],
            modules: [
                {
                    type_id: 12271, name: 'Energy neutralizer', short: 'Neut', example: 'Heavy Energy Neutralizer II',
                    impacts: [
                        { title: 'Drains their capacitor', detail: 'Repairs, hardeners, points and capacitor-hungry guns stop when it runs out.' },
                        { title: 'Optimal range and falloff', detail: 'Past optimal it drains less. At two falloffs it drains almost nothing.' },
                        { title: 'Costs your capacitor', detail: 'Every cycle uses some of yours. Keep an eye on your own capacitor.' },
                    ],
                    learn: { title: 'Watch on EVE Academy', url: ACADEMY_NEUTS },
                    practice: { title: 'Practice in EVE Combat Sim', url: NEUTS_SIM },
                },
                {
                    type_id: 12263, name: 'Nosferatu', short: 'Nos', example: 'Heavy Energy Nosferatu II',
                    impacts: [
                        { title: 'Free capacitor for you', detail: 'It moves capacitor from the target to you, and costs nothing to run.' },
                        { title: 'Only when you are lower', detail: 'It does nothing if you have more capacitor than the target, except on Blood Raider ships.' },
                        { title: 'Keeps your neuts running', detail: 'Leave it on all fight so you never run dry.' },
                    ],
                    practice: { title: 'Practice in EVE Combat Sim', url: NOS_SIM },
                },
                {
                    type_id: 41218, name: 'Cap battery', short: 'Battery', example: 'Republic Fleet Large Cap Battery',
                    impacts: [
                        { title: 'More capacitor', detail: 'A bigger pool lasts longer while your neuts cycle.' },
                        { title: 'Resists enemy neuts', detail: 'It cuts how much enemy neuts and nos take from you.' },
                        { title: 'Expect to be neuted back', detail: 'Enemy neut ships aim at ours. The battery is what keeps you running.' },
                    ],
                },
                {
                    type_id: 527, name: 'Stasis webifier', short: 'Web', example: 'Stasis Webifier II',
                    impacts: [
                        { title: 'Holds targets in range', detail: 'A slowed target can’t burn out of your neut range.' },
                        { title: 'Pins tackle', detail: 'A webbed frigate can’t orbit fast or get away.' },
                        { title: 'Helps the fleet hit', detail: 'Slow targets take more damage from guns and missiles.' },
                    ],
                    practice: { title: 'Practice in EVE Combat Sim', url: 'https://eve-cs.com/scenarios/basics/webs' },
                },
            ],
        },
        {
            id: 'counterplay',
            title: 'When they fight back',
            summary: 'Cap boosters, chains and enemy neuts.',
            format: 'read',
            body: [
                'Targets refill from their own recharge, from cap boosters and, for Guardians, from a chain partner. One neut on a chained Guardian mostly annoys it. Enough neuts at once empties it.',
            ],
            steps: [
                'Stack neuts on a target until it stops, then move the rest on.',
                'A cap booster refills instantly. Keep neuting: each charge used is one less, and reloading takes time.',
                'Watch your own capacitor. A neut ship with no capacitor is just a target.',
            ],
        },
    ],
    mistakes: [
        { title: 'Neuting yourself dry', fix: 'Neuts cost your capacitor too. Run your nos before you need it.' },
        { title: 'Everyone on one target', fix: 'Once a ship is dry, extra neuts are wasted. Move to the next one.' },
        { title: 'Neuting from too far', fix: 'Two falloffs out you drain almost nothing. Close in, or leave it to a longer-range ship.' },
        { title: 'Stopping too early', fix: 'Low capacitor falls fast. Keep neuting until the target is dry.' },
    ],
    drills: [
        { id: 'neuts-sim', title: 'Fly Energy Neutralizers', how: 'In EVE Combat Sim: empty the Brutix’s capacitor before it kills your drones.', kind: 'setup' },
        { id: 'nos-sim', title: 'Fly Nosferatu (Nos)', how: 'In EVE Combat Sim: keep your own capacitor up with nos.', kind: 'setup' },
        { id: 'fleet-neut', title: 'Neut on a fleet', how: 'Fly a neut ship on any fleet and drain the targets the FC calls.', kind: 'fleet' },
    ],
    resources: [
        { kind: 'guide', title: 'Skill plans', source: 'Minmatar Fleet', why: 'The alliance skill plans for doctrine hulls, neut ships included.', url: '/learning/skillplans/' },
        { kind: 'video', title: 'Newbee Tuesday: capacitor warfare', source: 'Imperium News · 2015', why: 'Neuts and nos explained. Older, still right on the basics.', url: 'https://www.youtube.com/watch?v=vYiUIvjVqrM' },
        { kind: 'video', title: 'Using energy neutralizers effectively', source: 'EVE Pro Guides · 2012', why: 'Tactics that still hold up. Ranges are from before the 2015 falloff change.', url: 'https://www.youtube.com/watch?v=6L1HfB_lp-o' },
        { kind: 'ccp', title: 'Energy neutralisers', source: 'EVE Academy · CCP Games', why: 'CCP’s short explainer, with the clip from this guide.', url: ACADEMY_NEUTS },
        { kind: 'wiki', title: 'Capacitor warfare', source: 'EVE University wiki', why: 'Neut versus nos and every hull on this ladder.', url: 'https://wiki.eveuniversity.org/Capacitor_warfare' },
        { kind: 'wiki', title: 'Capacitor', source: 'EVE University wiki', why: 'The recharge curve, and why low capacitor is hard to recover.', url: 'https://wiki.eveuniversity.org/Capacitor' },
        { kind: 'sim', title: 'Energy Neutralizers', source: 'EVE Combat Sim', why: 'Drain a dual-rep Brutix in your browser.', url: NEUTS_SIM },
        { kind: 'sim', title: 'Nosferatu (Nos)', source: 'EVE Combat Sim', why: 'When a nos drains, and when it does nothing.', url: NOS_SIM },
        { kind: 'tool', title: 'Pyfa', source: 'pyfa-org on GitHub', why: 'Graph your own capacitor under neut pressure.', url: 'https://github.com/pyfa-org/Pyfa' },
    ],
}
