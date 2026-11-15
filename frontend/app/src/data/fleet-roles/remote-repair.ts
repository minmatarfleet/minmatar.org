import type { FleetRoleGuide } from './types'

const CAP_CHAIN_LOGI = 'https://eve-cs.com/scenarios/logistics/cap-chain-logistics'

export const remote_repair: FleetRoleGuide = {
    slug: 'remote-repair',
    guide_slug: 'remote-repair-guide',
    name: 'Remote Repair',
    short_name: 'Logi',
    lede: 'Keep the fleet alive. Repair broadcasts fast, hold your cap chain, and stay on the logi anchor.',
    tagline: 'Keep the fleet alive.',
    capabilities: ['Logistics'],
    hero_type_id: 11987,
    read_minutes: 15,
    why: [
        'Logistics decide how long a fight lasts. Every ship the enemy calls has to die faster than you can repair it, and every one that lives gives our damage more time.',
        'Good logi is mostly speed: the seconds between a broadcast and your first repair. The rest is staying where your repairs reach everyone.',
        'Every strategic fleet needs logi, and you can start in a cheap Tech I cruiser.',
    ],
    why_video: { youtube_id: 'xK02SAZbeaU', title: 'Intro to Logi', source: 'Amoni Panala · EVE University class · 2024' },
    ladder: [],
    ships_from_doctrines: 'logistics',
    // Guardian, Zarmazd, Exequror, Augoror.
    ships_only: [11987, 49713, 634, 625],
    lessons: [
        {
            id: 'logi-anchoring',
            title: 'Anchoring',
            summary: 'Stay on the logi anchor so your repairs reach everyone.',
            format: 'read',
            body: [
                'Logistics fly together on their own anchor, usually a logi pilot the logi FC names. That keeps you in range of each other and of the fleet.',
            ],
            lists: [
                {
                    title: 'Important',
                    items: [
                        'Anchor on the <strong>logi anchor</strong>, not the fleet anchor, unless the FC says otherwise.',
                        'Keep the fleet inside your repair range. If it moves out of range, say so in the logi channel.',
                        '<strong>Never burn toward a broadcast.</strong> Chasing one ship pulls you out of range of everyone else.',
                    ],
                },
                {
                    title: 'Common problems',
                    items: [
                        '<strong>You are the target:</strong> broadcast, stay on the anchor, and let the other logi repair you.',
                        '<strong>The logi anchor is tackled or dies:</strong> anchor on the next pilot the logi FC calls.',
                        '<strong>You lose your partner:</strong> say it in the logi channel and get a new one.',
                    ],
                },
            ],
        },
        {
            id: 'repairing-broadcasts',
            title: 'Repairing from broadcasts',
            summary: 'Lock fast, repair early, and know which broadcasts to skip.',
            format: 'video',
            video: { youtube_id: '19BRVGPREnQ', title: 'PVP Skills: Logistics 101', source: 'Murda Mike · The Brave Dojo · 2023' },
            body: [
                'Every second between a broadcast and your first repair is armor the pilot doesn’t get back. Armor repairs land at the end of each cycle, so start early.',
            ],
            steps: [
                'Put your logi partners and the fleet anchor on your watchlist.',
                'Lock broadcasts in the order they come in, and start a repairer as soon as the lock lands.',
                'Lock pilots the enemy starts locking (yellow boxes) before they broadcast.',
                'Turn repairs off a pilot who is back to full, so your capacitor goes where it’s needed.',
            ],
            donts: [
                '<strong>Don’t chase bomb or smartbomb broadcasts.</strong> The damage hits everyone at once and is over before your repairs land. Look for the pilot who is still taking damage.',
                'Don’t call broadcasts on fleet comms. Logi talk goes in the logi channel.',
            ],
            links: [
                { kind: 'video', title: 'Hotkeys: all the broadcasts', source: 'Fua Consternation · 2021', why: 'Bind a key to lock the broadcasting pilot.', url: 'https://www.youtube.com/watch?v=NlWlLgU9k8w' },
            ],
        },
        {
            id: 'staggering-repairs',
            title: 'Staggering repairs',
            summary: 'Start with everything, then spread your cycles out.',
            format: 'read',
            body: [
                'When a pilot is first called, every repairer you have lands at once to stop the damage. Once their armor holds, spread your repairers out so a repair lands every few seconds instead of all together.',
            ],
            steps: [
                'On a new broadcast, <strong>start every repairer at once</strong>. The first cycles land together and stop the damage.',
                'Once their armor holds, <strong>stagger off</strong>: stop one repairer and restart it partway through the others’ cycle.',
                'Keep the cycles spread out. Armor stays steady, and you always have a repairer about to finish that you can move to the next broadcast.',
            ],
            donts: [
                'Don’t leave every repairer on a pilot who is already full. Spread them out or move them to the next broadcast.',
            ],
        },
        {
            id: 'cap-chains',
            title: 'Capacitor chains',
            summary: 'Guardian partners, who gives to whom, and what to do when one dies.',
            format: 'video',
            video: { youtube_id: 'g0ikhpmou6Q', title: 'Logi 101 and cap chain practice', source: 'Jinx De’Caire · The Brave Dojo · 2020' },
            practice: { kind: 'sim', title: 'Cap Chain Logistics', source: 'EVE Combat Sim', why: 'Hold a capacitor chain with other Guardians while the fleet takes damage.', url: CAP_CHAIN_LOGI },
            body: [
                'Guardians can’t run their repairers on their own capacitor. They pair up, or form a chain, and each keeps a capacitor transmitter on a partner. Each gives what the other uses.',
            ],
            steps: [
                'Get your partner, or your place in the chain, from the logi FC at form-up.',
                'Lock your partner first. Keep your transmitter on them all fleet, even when nothing is shooting.',
                'Answer capacitor checks in the logi channel with a number.',
                'If you are being neuted, or your partner dies, say it in the logi channel right away.',
            ],
            links: [
                { kind: 'wiki', title: 'Logistics', source: 'EVE University wiki', why: 'Capacitor chains, the watchlist and broadcasts in more detail.', url: 'https://wiki.eveuniversity.org/Logistics' },
            ],
        },
        {
            id: 'logi-fit',
            title: 'Your logi fit',
            summary: 'The modules on our logi fits and what each one does in a fight.',
            format: 'read',
            body: [
                'Our logi fits use the same few modules. Pick one below to see what it does.',
            ],
            modules: [
                {
                    type_id: 26914, name: 'Remote armor repairer', short: 'Armor rep', example: 'Large Remote Armor Repairer II',
                    impacts: [
                        { title: 'Lands at the end of the cycle', detail: 'The armor comes back when the cycle finishes, so start repairing before the pilot is low.' },
                        { title: 'Optimal range and falloff', detail: 'Past optimal range, each cycle repairs less. Keep the fleet inside your optimal.' },
                        { title: 'Overheat to save a pilot', detail: 'Heat makes it cycle faster, but burns the module. Use it in short bursts.' },
                    ],
                },
                {
                    type_id: 16487, name: 'Remote capacitor transmitter', short: 'Cap', example: 'Large Inductive Compact Remote Capacitor Transmitter',
                    impacts: [
                        { title: 'Keeps your partner running', detail: 'Your partner’s repairers use the capacitor you send them.' },
                        { title: 'Always on', detail: 'Leave it running all fleet, so nobody has to catch up when the shooting starts.' },
                        { title: 'Helps against neuts', detail: 'A neuted logi can keep repairing if someone moves a transmitter onto them.' },
                    ],
                    practice: { title: 'Practice in EVE Combat Sim', url: CAP_CHAIN_LOGI },
                },
                {
                    type_id: 1952, name: 'Sensor booster', short: 'Sensor', example: 'Sensor Booster II',
                    impacts: [
                        { title: 'Scan resolution script', detail: 'Locks faster, so your first repair lands sooner. Load this one by default.' },
                        { title: 'Targeting range script', detail: 'Reaches broadcasts across a spread-out fleet.' },
                        { title: 'ECCM script', detail: 'Makes you harder to jam when the enemy brings ECM.' },
                    ],
                },
                {
                    type_id: 49774, name: 'Mutadaptive remote armor repairer', short: 'Zarmazd rep', example: 'Perun Heavy Mutadaptive Remote Armor Repairer',
                    impacts: [
                        { title: 'Grows on one target', detail: 'It repairs more every cycle it stays on the same pilot.' },
                        { title: 'Switching starts over', detail: 'A new target resets it. Only switch for a pilot in more danger.' },
                        { title: 'Leave fast switches to Guardians', detail: 'Hold the anchor or a tanky ship, and let the Guardians chase the broadcasts.' },
                    ],
                    learn: { title: 'Read on EVE University', url: 'https://wiki.eveuniversity.org/Zarmazd' },
                },
                {
                    type_id: 3568, name: 'Capacitor booster', short: 'Cap booster', example: 'Small Capacitor Booster II',
                    impacts: [
                        { title: 'Capacitor on demand', detail: 'Each charge adds capacitor at once. The Zarmazd uses one instead of a chain.' },
                        { title: 'Beats neuts', detail: 'Inject when you are neuted, and keep repairing.' },
                        { title: 'Watch your charges', detail: 'When the charges run out, so does your capacitor. Carry the spares from the fit.' },
                    ],
                },
            ],
        },
        {
            id: 'specialty-roles',
            title: 'Specialty roles',
            summary: 'Logi anchor, capacitor truck and boosh defense: jobs the logi FC hands out.',
            format: 'read',
            body: [
                'On bigger fleets, the logi FC gives a few logi pilots an extra job. Only take one when you are asked, and say in the logi channel when you can’t keep doing it.',
            ],
            lists: [
                {
                    title: 'Logi anchor',
                    type_id: 11987,
                    items: [
                        'The other logi anchor on you, so <strong>where you go, the logi wing goes</strong>.',
                        'Keep the range to the fleet the logi FC calls, and move smoothly so the wing can follow.',
                        'Call your moves in the logi channel before you make them, and say it at once if you get tackled.',
                    ],
                },
                {
                    title: 'Capacitor truck',
                    type_id: 12102,
                    items: [
                        'Your job is capacitor, not repairs. <strong>Keep your transmitters on whoever needs cap most</strong>, for example:',
                        '<strong>Anyone broadcasting for capacitor.</strong> Lock capacitor broadcasts like repair broadcasts.',
                        '<strong>Whoever is being primaried.</strong>',
                        '<strong>Whoever the enemy is neuting.</strong> A logi with no capacitor can’t repair anyone.',
                        '<strong>Specialty ships</strong> that need capacitor for their job, like firewall Nestors and neut Bhaalgorns.',
                        'Answer cap calls in the logi channel, and say when your own capacitor runs low.',
                    ],
                },
                {
                    title: 'Boosh defense',
                    type_id: 448,
                    items: [
                        'Enemy command destroyers boosh our logi away from the fleet with a micro jump field generator.',
                        '<strong>A scrammed command destroyer can’t boosh.</strong> Our Zarmazd fit carries a Warp Scrambler II in cargo: fit it when the logi FC calls for boosh defense.',
                        'Scram any command destroyer that comes close to the logi wing, and call it in the logi channel.',
                    ],
                },
            ],
            links: [
                { kind: 'guide', title: 'Fleet Disruption', source: 'Minmatar Fleet', why: 'How booshing works, from the command destroyer’s side.', url: '/learning/guides/fleet-disruption-guide/' },
            ],
        },
    ],
    mistakes: [
        { title: 'Chasing the broadcast', fix: 'Burning toward one ship pulls you off the anchor and out of range of everyone else.' },
        { title: 'Waiting for the broadcast', fix: 'Lock pilots the enemy starts locking. Your first repair lands a cycle earlier.' },
        { title: 'Breaking the chain', fix: 'A Guardian that stops transmitting starves its partner. Keep the transmitter on all fleet.' },
        { title: 'Chasing bomb and smartbomb damage', fix: 'It is over before your repairs land. Look for the pilot who is still taking damage.' },
        { title: 'Switching the Zarmazd too early', fix: 'A new target resets its repairs. Only switch for a pilot in more danger.' },
    ],
    drills: [
        { id: 'cap-chain-sim', title: 'Fly Cap Chain Logistics', how: 'In EVE Combat Sim: hold the chain while the fleet takes damage.', kind: 'setup' },
        { id: 'fleet-logi', title: 'Fly logi on a fleet', how: 'Any logistics hull from Ships we fly, repairing from broadcasts.', kind: 'fleet' },
        { id: 'fleet-chain', title: 'Hold a capacitor chain for a whole fleet', how: 'With the same partner from form-up to dock.', kind: 'fleet' },
    ],
    resources: [
        { kind: 'guide', title: 'New Player Fleet Guide', source: 'Minmatar Fleet', why: 'Broadcasting for repairs and what the logi channel is for.', url: '/learning/guides/new-player-fleet-guide/' },
        { kind: 'guide', title: 'Faction Warfare Battlefields', source: 'Minmatar Fleet', why: 'Logi on a battlefield, and why they are always welcome.', url: '/learning/guides/faction-warfare-battlefields/' },
        { kind: 'video', title: 'How to die in EVE Online', source: 'Minmatar Fleet training video', why: 'Our own training video: the mistakes that get pilots killed on our fleets.', url: 'https://www.youtube.com/watch?v=sP-iIc6nn5k' },
        { kind: 'video', title: 'PVP Skills: Logistics 101', source: 'Murda Mike · The Brave Dojo · 2023', why: 'A full logi class: locking, broadcasts, positioning.', url: 'https://www.youtube.com/watch?v=19BRVGPREnQ' },
        { kind: 'video', title: 'Intro to Logi', source: 'Amoni Panala · EVE University class · 2024', why: 'The basics from a teaching corporation.', url: 'https://www.youtube.com/watch?v=xK02SAZbeaU' },
        { kind: 'video', title: 'Horde Flightschool: logi anchoring', source: 'Pandemic Horde · 2017', why: 'Anchoring in a big fleet, still how it works.', url: 'https://www.youtube.com/watch?v=XrIBa8vOng8' },
        { kind: 'wiki', title: 'Logistics', source: 'EVE University wiki', why: 'Capacitor chains, the watchlist, broadcasts and anchoring.', url: 'https://wiki.eveuniversity.org/Logistics' },
        { kind: 'sim', title: 'Cap Chain Logistics', source: 'EVE Combat Sim', why: 'Hold a capacitor chain under fire.', url: CAP_CHAIN_LOGI },
        { kind: 'tool', title: 'Pyfa', source: 'pyfa-org on GitHub', why: 'Graph your remote repairs and capacitor stability.', url: 'https://github.com/pyfa-org/Pyfa' },
    ],
}
