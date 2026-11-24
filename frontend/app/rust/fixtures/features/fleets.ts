// Test data for the Features/Fleets stories: fleets, doctrines, invites, SRP, commanders.
// Typed with the components' own prop types, so `npm run check` fails when a prop changes.
// Story args reach the render server as JSON, so every Date below arrives as an ISO string,
// exactly as the API sends it; the blocks parse it themselves.
import type {
    FleetItem, FleetUI, DoctrineType, FittingItem, Tracking, FleetCompositionUI, FleetRadarUI,
    TribeGroupRefUI, SRPUI, FleetCombatLog, FleetTrackingTexts, BattlePilotRow,
} from '@dtypes/layout_components'
import type { FleetCommander, FleetCommanderMetrics, Contract, CandidateFleet, FleetTypes } from '@dtypes/api.minmatar.org'
import type { CommandStep } from '@helpers/fleet_command'
import type { FleetMining, FleetMiningEvent, FleetMiningTimeline } from '@helpers/api.minmatar.org/fleets'

// Countdown.astro's ticker calls a bare `pad()` that nothing on the page defines (src/components/blocks/Countdown.astro),
// so it throws a ReferenceError every second. A stand-in keeps the stories' output clean until that is fixed.
const w = globalThis as { pad?: (num: number) => string | number }
if (!w.pad) w.pad = (num: number) => (num < 10 ? `0${num}` : num)

const HOUR = 3_600_000
const DAY = 24 * HOUR

/** A moment relative to now, so "upcoming" fleets stay upcoming and "active" ones stay running. */
export const from_now = (ms: number) => new Date(Date.now() + ms)
export const in_hours = (hours: number) => from_now(hours * HOUR)
export const hours_ago = (hours: number) => from_now(-hours * HOUR)
export const days_ago = (days: number) => from_now(-days * DAY)

// --- Corporations and commanders ------------------------------------------------------

export const CORPS = {
    a_rat:  { corporation_id: 98726134, corporation_name: 'Rattini Tribe' },
    fosfo:  { corporation_id: 98726135, corporation_name: 'Fraternity of the Old Spice Frigate Order' },
    tdt:    { corporation_id: 98726136, corporation_name: 'The Dark Tribe' },
    sltar:  { corporation_id: 98726137, corporation_name: 'Sleipnir Tactical Reserve' },
} as const

export const FCS = {
    keldar:   { id: 2112954532, name: "Kel'dar Atram", ...CORPS.a_rat },
    vaenne:   { id: 2112954533, name: 'Vaenne Hroth', ...CORPS.fosfo },
    tarsus:   { id: 2112954534, name: 'Tarsus Rennir', ...CORPS.tdt },
    brakka:   { id: 2112954535, name: 'Brakka Sundowner', ...CORPS.a_rat },
    ilsa:     { id: 2112954536, name: 'Ilsa Verhaaren', ...CORPS.sltar },
    long_one: { id: 2112954537, name: 'Bartholomew-Alexander of the Heimatar Highlands the Third', ...CORPS.fosfo },
} as const

// --- Doctrines ---------------------------------------------------------------------------

const fitting = (id: number, name: string, ship_id: number, ship_name: string, ship_type: string, fitting_type: string): FittingItem => ({
    id,
    fitting_name: name,
    fitting_type,
    ship_id,
    ship_name,
    ship_type,
    ship_meta: 'Tech I',
    eft_format: `[${ship_name}, ${name}]\n\n200mm AutoCannon II\n`,
})

export const HURRICANE_FIT = fitting(301, 'Hurricane - Rens Brawl', 24702, 'Hurricane', 'Combat Battlecruiser', 'primary')
export const MUNINN_FIT = fitting(302, 'Muninn - Long Range', 12015, 'Muninn', 'Heavy Assault Cruiser', 'primary')
export const SCIMITAR_FIT = fitting(303, 'Scimitar - Logi', 11978, 'Scimitar', 'Logistics', 'support')
export const STABBER_FIT = fitting(304, 'Stabber - Academy', 622, 'Stabber', 'Cruiser', 'primary')
export const RIFTER_FIT = fitting(305, 'Rifter - Frigate Swarm', 587, 'Rifter', 'Frigate', 'primary')

const doctrine = (id: number, name: string, type: DoctrineType['type'], primary: FittingItem[], support: FittingItem[] = []): DoctrineType => ({
    id,
    name,
    type,
    created_at: days_ago(90),
    updated_at: days_ago(7),
    description: `${name} is the alliance's standing answer in the Amarr–Minmatar warzone.`,
    primary_fittings: primary,
    secondary_fittings: [],
    support_fittings: support,
    utility_fittings: [],
    capitals_fittings: [],
    location_ids: [30002510, 30002537],
})

export const hurricane_doctrine = doctrine(12, 'Hurricane Brawl', 'strategic', [HURRICANE_FIT], [SCIMITAR_FIT])
export const muninn_doctrine = doctrine(13, 'Muninn Kite', 'non_strategic', [MUNINN_FIT, HURRICANE_FIT], [SCIMITAR_FIT])
export const academy_doctrine = doctrine(14, 'Frigate Academy', 'experimental', [RIFTER_FIT, STABBER_FIT])

/** One contract line per fitting, as the supply tracker returns them. */
export const supply_contracts: Contract[] = [HURRICANE_FIT, SCIMITAR_FIT].map((fit, index) => ({
    expectation_id: 40 + index,
    title: fit.fitting_name,
    fitting_id: fit.id,
    ship_id: fit.ship_id,
    structure_id: null,
    location_id: 30002510,
    location_name: 'Rens',
    desired_quantity: 30,
    current_quantity: index === 0 ? 24 : 0,
    readiness: index === 0 ? 'ready' : 'empty',
    sellers: [],
    latest_contract_timestamp: null,
    doctrines: [],
}))

// --- Tribe group hosts -------------------------------------------------------------------

export const skirmishers: TribeGroupRefUI = { id: 21, code: 'SKIR', name: 'Skirmishers', tribe_id: 4, tribe_name: 'Pulse' }
export const capitals: TribeGroupRefUI = { id: 7, code: 'CAPS', name: 'Capital Pilots', tribe_id: 2, tribe_name: 'Capitals' }

// --- Fleets ------------------------------------------------------------------------------

const base_fleet = (overrides: Partial<FleetItem> & Pick<FleetItem, 'id'>): FleetItem => ({
    type: 'non_strategic',
    audience: 'FL33T',
    doctrine_id: hurricane_doctrine.id,
    start_time: in_hours(30),
    fleet_commander_id: FCS.keldar.id,
    fleet_commander_name: FCS.keldar.name,
    fleet_commander_fleet_count: 41,
    corporation_id: FCS.keldar.corporation_id,
    corporation_name: FCS.keldar.corporation_name,
    location: 'Amamake - Freeport',
    objective: 'Roam Heimatar and fight whatever the Amarr send.',
    status: 'pending',
    ...overrides,
})

const tracking = (id: number, started: Date, ended: Date | null): Tracking => ({
    id,
    start_time: started,
    end_time: ended,
    is_registered: true,
    is_free_move: true,
    has_motd: true,
})

export const upcoming_strategic: FleetItem = base_fleet({
    id: 9401,
    type: 'strategic',
    members_count: 18,
    start_time: in_hours(26),
    description: '**Form up on the Rens undock.** Bring the fit from the doctrine page, filled with T2 ammo.',
    objective: 'Strategic operation: take back the Amamake gate camp before the Amarr reinforce it.',
    campaign_slug: 'amamake-2026-11',
    campaign_name: 'Amamake Offensive',
})

export const upcoming_training: FleetItem = base_fleet({
    id: 9402,
    type: 'training',
    fleet_commander_id: FCS.vaenne.id,
    fleet_commander_name: FCS.vaenne.name,
    corporation_id: FCS.vaenne.corporation_id,
    corporation_name: FCS.vaenne.corporation_name,
    fleet_commander_fleet_count: 12,
    doctrine_id: academy_doctrine.id,
    location: 'Rens - Brutor Tribe Treasury',
    start_time: in_hours(52),
    objective: 'First-week pilots welcome. We will walk through d-scan, anchoring and broadcasting.',
})

export const upcoming_npsi: FleetItem = base_fleet({
    id: 9403,
    type: 'npsi',
    fleet_commander_id: FCS.brakka.id,
    fleet_commander_name: FCS.brakka.name,
    corporation_id: FCS.brakka.corporation_id,
    corporation_name: FCS.brakka.corporation_name,
    fleet_commander_fleet_count: 63,
    location: 'Auga - Freeport',
    start_time: in_hours(75),
    objective: 'NPSI roam through Hed: blue-ish locals, shoot reds.',
})

export const upcoming_non_strategic: FleetItem = base_fleet({
    id: 9404,
    type: 'non_strategic',
    fleet_commander_id: FCS.tarsus.id,
    fleet_commander_name: FCS.tarsus.name,
    corporation_id: FCS.tarsus.corporation_id,
    corporation_name: FCS.tarsus.corporation_name,
    fleet_commander_fleet_count: 27,
    doctrine_id: muninn_doctrine.id,
    members_count: 9,
    location: 'Rens - Brutor Tribe Treasury',
    start_time: in_hours(100),
})

export const tribe_fleet: FleetItem = base_fleet({
    id: 9405,
    type: 'non_strategic',
    fleet_commander_id: FCS.ilsa.id,
    fleet_commander_name: FCS.ilsa.name,
    corporation_id: FCS.ilsa.corporation_id,
    corporation_name: FCS.ilsa.corporation_name,
    fleet_commander_fleet_count: 9,
    location: 'Vard - Freeport',
    start_time: in_hours(120),
    objective: 'Skirmishers practice night: small gang, fast ships.',
    host_group: skirmishers,
    open_to_alliance: false,
})

export const open_tribe_fleet: FleetItem = {
    ...tribe_fleet,
    id: 9406,
    host_group: capitals,
    open_to_alliance: true,
    on_schedule: true,
    objective: 'Capitals hot-drop practice, open to anyone who wants to watch the cyno work.',
}

export const active_fleet: FleetItem = base_fleet({
    id: 9399,
    type: 'strategic',
    members_count: 36,
    start_time: hours_ago(1.5),
    tracking: tracking(8801, hours_ago(1.4), null),
    status: 'active',
    objective: 'Defend the Amamake Freeport timer.',
})

export const completed_fleet: FleetItem = base_fleet({
    id: 9390,
    type: 'strategic',
    members_count: 41,
    start_time: new Date('2026-11-14T19:00:00Z'),
    tracking: tracking(8790, new Date('2026-11-14T19:04:00Z'), new Date('2026-11-14T21:31:00Z')),
    status: 'complete',
    objective: 'Amamake gate camp. 41 flew, 112 kills, 9 losses.',
    aar_link: 'https://forums.minmatar.org/aar/9390',
})

export const cancelled_fleet: FleetItem = base_fleet({
    id: 9391,
    type: 'training',
    start_time: new Date('2026-11-12T18:00:00Z'),
    status: 'cancelled',
    objective: 'Cancelled: the FC got a real-life emergency.',
})

export const fleet_on_alt: FleetItem = base_fleet({
    id: 9407,
    fleet_commander_alt_id: 2112954599,
    fleet_commander_alt_name: 'Kel Scout Alt',
    start_time: in_hours(10),
})

export const fleet_with_long_text: FleetItem = base_fleet({
    id: 9408,
    type: 'strategic',
    fleet_commander_id: FCS.long_one.id,
    fleet_commander_name: FCS.long_one.name,
    corporation_id: FCS.long_one.corporation_id,
    corporation_name: FCS.long_one.corporation_name,
    location: 'Old Man Star - The Honorable Order of the Very Long Station Names, Docking Tower Seventeen',
    start_time: in_hours(6),
    objective: 'Escort the freight convoy from Jita through Hek to Rens, then hold the Amamake perimeter, then if there is time shoot the Amarr logistics wing near the Sasen constellation gate. '.repeat(2),
    description: 'Bring **two** of the fits. Read the doctrine page. Read it again.\n\n- Fill cargo with T2 ammo\n- Undock at Rens, then head to Amamake\n- Voice is mandatory',
})

/** A fleet with only the fields the API always sends: no type, corp, location, objective or counts. */
export const bare_fleet: FleetItem = {
    id: 9409,
    audience: 'FL33T',
    doctrine_id: 0,
    start_time: in_hours(40),
    fleet_commander_id: FCS.vaenne.id,
    fleet_commander_name: FCS.vaenne.name,
}

export const typical_fleets: FleetItem[] = [
    upcoming_strategic, upcoming_training, upcoming_npsi, upcoming_non_strategic, tribe_fleet,
]

const busy_templates = [upcoming_strategic, upcoming_training, upcoming_npsi, upcoming_non_strategic, tribe_fleet, open_tribe_fleet]
const busy_fcs = Object.values(FCS).slice(0, 5)

/** 24 scheduled fleets across the week, as the hub shows on a busy weekend. */
export const busy_fleets: FleetItem[] = Array.from({ length: 24 }, (_, index) => {
    const template = busy_templates[index % busy_templates.length]
    const fc = busy_fcs[index % busy_fcs.length]
    return {
        ...template,
        id: 9500 + index,
        fleet_commander_id: fc.id,
        fleet_commander_name: fc.name,
        corporation_id: fc.corporation_id,
        corporation_name: fc.corporation_name,
        start_time: in_hours(4 + index * 5),
        members_count: index % 3 === 0 ? 12 + index : undefined,
    }
})

/** The end time and duration lines a completed fleet shows (what `get_fleet_tracking_texts` builds). */
export const completed_tracking_texts: FleetTrackingTexts = {
    fleet_end_eve_time_text: 'Nov 14, 2026, 21:31',
    fleet_duration_text: '2h 27m',
    fleet_tracking_hint: 'From Nov 14, 2026, 19:04 to Nov 14, 2026, 21:31',
}

/** The tooltip each fleet type's flag carries. */
export const FLEET_TYPE_LABELS: Record<FleetTypes, string> = {
    strategic: 'Strategic fleet',
    non_strategic: 'Non strategic fleet',
    training: 'Training fleet',
    npsi: 'NPSI fleet',
}

export const history_fleets: FleetItem[] = [completed_fleet, {
    ...completed_fleet,
    id: 9380,
    type: 'training',
    fleet_commander_id: FCS.vaenne.id,
    fleet_commander_name: FCS.vaenne.name,
    corporation_id: FCS.vaenne.corporation_id,
    corporation_name: FCS.vaenne.corporation_name,
    start_time: new Date('2026-11-10T18:00:00Z'),
    tracking: tracking(8780, new Date('2026-11-10T18:03:00Z'), new Date('2026-11-10T19:40:00Z')),
    members_count: 14,
    objective: 'Academy night: 14 new pilots.',
}, cancelled_fleet]

export const fc_metrics: FleetCommanderMetrics[] = [
    { user_id: 1, primary_character_id: FCS.keldar.id, primary_character_name: FCS.keldar.name, corporation_id: FCS.keldar.corporation_id, corporation_name: FCS.keldar.corporation_name, fleet_count: 41 },
    { user_id: 2, primary_character_id: FCS.brakka.id, primary_character_name: FCS.brakka.name, corporation_id: FCS.brakka.corporation_id, corporation_name: FCS.brakka.corporation_name, fleet_count: 33 },
    { user_id: 3, primary_character_id: FCS.tarsus.id, primary_character_name: FCS.tarsus.name, corporation_id: FCS.tarsus.corporation_id, corporation_name: FCS.tarsus.corporation_name, fleet_count: 27 },
]

// --- Full fleet (the fleet page) ---------------------------------------------------------

const full_fleet = (overrides: Partial<FleetUI>): FleetUI => ({
    id: 9401,
    type: 'strategic',
    description: '**Form up on the Rens undock.** Bring the fit from the doctrine page.',
    objective: 'Strategic operation: take back the Amamake gate camp.',
    start_time: in_hours(26),
    fleet_commander_id: FCS.keldar.id,
    fleet_commander_name: FCS.keldar.name,
    location: 'Amamake - Freeport',
    doctrine: hurricane_doctrine,
    doctrine_id: hurricane_doctrine.id,
    tracking: null as unknown as Tracking,
    audience: 'FL33T',
    disable_motd: false,
    hide_volunteers: false,
    status: 'pending',
    aar_link: '',
    ...overrides,
})

/** A standard fleet the viewer was invited to and has not answered yet. */
export const invited_fleet = full_fleet({ my_invite_answer: 'pending', my_invite_source: 'pilot', my_invite_wave: 1 })
export const invited_in_fleet = full_fleet({ my_invite_answer: 'in', my_invite_source: 'pilot', my_invite_wave: 1 })
export const invited_out_fleet = full_fleet({ my_invite_answer: 'out', my_invite_source: 'pilot', my_invite_wave: 1 })
export const invited_new_pilot_fleet = full_fleet({ my_invite_answer: 'pending', my_invite_source: 'first_week', my_invite_wave: 2 })
export const invited_started_fleet = full_fleet({
    my_invite_answer: 'pending',
    my_invite_source: 'pilot',
    tracking: tracking(8801, hours_ago(1), null),
    status: 'active',
})

export const private_fleet = full_fleet({
    invite_only: true,
    discord_thread_url: 'https://discord.com/channels/1000000000000000000/1100000000000000000',
    my_invite_answer: 'pending',
    my_invite_wave: 2,
    my_invite_source: 'pilot',
    can_manage_invites: false,
})
export const private_fleet_manager = full_fleet({
    invite_only: true,
    discord_thread_url: 'https://discord.com/channels/1000000000000000000/1100000000000000000',
    my_invite_answer: null,
    can_manage_invites: true,
})
export const private_fleet_sitting_out = { ...private_fleet, my_invite_answer: 'out' }
export const private_fleet_no_thread = { ...private_fleet, discord_thread_url: null }

// --- Checklist ---------------------------------------------------------------------------

export const steps_fresh: CommandStep[] = [
    { key: 'scheduled', label: 'Scheduled', short_label: 'Scheduled', detail: '19:00 EVE', state: 'done' },
    { key: 'ships', label: 'Ships set', short_label: 'Set ships', detail: 'Hurricane Brawl', state: 'done' },
    { key: 'start', label: 'Form up, then start the fleet', short_label: 'Form up', detail: 'Make the fleet in game first. Starting sends the start ping and looks you up in game.', state: 'next' },
    { key: 'advert', label: 'Fleet Finder advert', short_label: 'Advert', detail: 'Checked once the fleet is tracking.', state: 'todo' },
    { key: 'free_move', label: 'Free move', short_label: 'Free move', detail: 'Checked once the fleet is tracking.', state: 'todo' },
    { key: 'motd', label: 'MOTD', short_label: 'MOTD', detail: 'Checked once the fleet is tracking.', state: 'todo' },
]

export const steps_no_ships: CommandStep[] = [
    steps_fresh[0],
    { ...steps_fresh[1], detail: 'Not set: choose a doctrine or a custom lineup on the Ships tab', state: 'next' },
    ...steps_fresh.slice(2).map((step): CommandStep => ({ ...step, state: 'todo' })),
]

export const steps_tracking: CommandStep[] = [
    steps_fresh[0],
    steps_fresh[1],
    { ...steps_fresh[2], label: 'Pinged and tracking', short_label: 'Tracking', detail: 'since 19:04 EVE', state: 'done' },
    { ...steps_fresh[3], detail: 'Posted', state: 'done' },
    { ...steps_fresh[4], detail: 'Off: turn on Free-move in the fleet window', state: 'next' },
    { ...steps_fresh[5], detail: 'Not set yet: use Refresh MOTD below', state: 'todo' },
]

export const steps_all_done: CommandStep[] = steps_tracking.map((step): CommandStep => ({
    ...step,
    state: 'done',
    detail: step.key === 'free_move' ? 'On' : step.key === 'motd' ? 'Set' : step.detail,
}))

// --- Composition -------------------------------------------------------------------------

const pilot = (id: number, name: string) => ({ character_id: id, character_name: name })

export const composition: FleetCompositionUI[] = [
    {
        ship_type_id: 24702,
        ship_type_name: 'Hurricane',
        members: [
            pilot(2112954532, "Kel'dar Atram"), pilot(2112954534, 'Tarsus Rennir'), pilot(2112954535, 'Brakka Sundowner'),
            pilot(2112954540, 'Hek Roamer'), pilot(2112954541, 'Amamake Defender'), pilot(2112954542, 'Rens Local'),
        ],
    },
    {
        ship_type_id: 11978,
        ship_type_name: 'Scimitar',
        members: [pilot(2112954536, 'Ilsa Verhaaren'), pilot(2112954543, 'Logi Lorrin')],
    },
    {
        ship_type_id: 12015,
        ship_type_name: 'Muninn',
        members: [pilot(2112954533, 'Vaenne Hroth')],
    },
]

export const radar: FleetRadarUI[] = [
    {
        solar_system_id: 30002537,
        solar_system_name: 'Amamake',
        start_type_id: 3802,
        jumps: 0,
        members: composition[0].members.slice(0, 4),
    },
    {
        solar_system_id: 30002510,
        solar_system_name: 'Rens',
        start_type_id: 7,
        jumps: 3,
        members: [...composition[1].members, ...composition[2].members],
    },
]

/** 30 hulls, to see a roster that wraps over several rows. */
export const busy_composition: FleetCompositionUI[] = [
    { ship_type_id: 24702, ship_type_name: 'Hurricane', members: Array.from({ length: 18 }, (_, i) => pilot(2112960000 + i, `Hurricane Pilot ${i + 1}`)) },
    { ship_type_id: 11978, ship_type_name: 'Scimitar', members: Array.from({ length: 6 }, (_, i) => pilot(2112961000 + i, `Logi Pilot ${i + 1}`)) },
    { ship_type_id: 12015, ship_type_name: 'Muninn', members: Array.from({ length: 4 }, (_, i) => pilot(2112962000 + i, `Muninn Pilot ${i + 1}`)) },
    { ship_type_id: 587, ship_type_name: 'Rifter', members: [pilot(2112963000, 'Rifter Rookie')] },
]

// --- Commanders --------------------------------------------------------------------------

const commander = (user_id: number, who: (typeof FCS)[keyof typeof FCS], extra: Partial<FleetCommander>): FleetCommander => ({
    user_id,
    primary_character_id: who.id,
    primary_character_name: who.name,
    corporation_id: who.corporation_id,
    corporation_name: who.corporation_name,
    fleets_total: 0,
    fleets_this_month: 0,
    last_led: null,
    rank_name: null,
    rank_order: null,
    timezone: { brackets: ['EU'], secondary: [], source: 'calculated', weekend: [] },
    ...extra,
})

export const commanders: FleetCommander[] = [
    commander(1, FCS.keldar, { rank_name: 'Strategic FC', rank_order: 1, fleets_total: 112, fleets_this_month: 9, last_led: hours_ago(5).toISOString(), timezone: { brackets: ['EU', 'US'], secondary: [], source: 'calculated', weekend: [] } }),
    commander(2, FCS.brakka, { rank_name: 'Strategic FC', rank_order: 1, fleets_total: 87, fleets_this_month: 6, last_led: days_ago(1).toISOString(), timezone: { brackets: ['US'], secondary: [], source: 'declared', weekend: [] } }),
    commander(3, FCS.tarsus, { rank_name: 'Skirmish FC', rank_order: 2, fleets_total: 27, fleets_this_month: 3, last_led: days_ago(6).toISOString(), timezone: { brackets: ['AU'], secondary: ['EU'], source: 'calculated', weekend: [] } }),
    commander(4, FCS.vaenne, { rank_name: 'Skirmish FC', rank_order: 2, fleets_total: 1, fleets_this_month: 1, last_led: days_ago(2).toISOString() }),
    commander(5, FCS.ilsa, { fleets_total: 0 }),
    commander(6, FCS.long_one, { fleets_total: 14, last_led: days_ago(30).toISOString() }),
]

// --- SRP ---------------------------------------------------------------------------------

const srp = (id: number, overrides: Partial<SRPUI>): SRPUI => ({
    id,
    fleet_id: 9390,
    combat_log_id: 0,
    not_tracked_in_fleet: false,
    external_killmail_link: `https://zkillboard.com/kill/1200000${id}/`,
    status: 'pending',
    character_id: 2112954540,
    character_name: 'Hek Roamer',
    primary_character_id: 2112954540,
    primary_character_name: 'Hek Roamer',
    ship_type_id: 24702,
    ship_name: 'Hurricane',
    killmail_id: 1200000000 + id,
    amount: 78_000_000,
    is_corp_ship: false,
    corporation_id: 98726134,
    corporation_name: 'Rattini Tribe',
    comments: '',
    category: 'dps',
    ship_type: 'Combat Battlecruiser',
    ...overrides,
})

export const srp_one: SRPUI[] = [srp(1, {})]

export const srp_typical: SRPUI[] = [
    srp(1, {}),
    srp(2, { character_id: 2112954541, character_name: 'Amamake Defender', primary_character_id: 2112954541, primary_character_name: 'Amamake Defender', ship_type_id: 11978, ship_name: 'Scimitar', category: 'logistics', ship_type: 'Logistics', amount: 120_000_000 }),
    srp(3, { character_id: 2112954542, character_name: 'Rens Local', primary_character_id: 2112954542, primary_character_name: 'Rens Local', ship_type_id: 12015, ship_name: 'Muninn', ship_type: 'Heavy Assault Cruiser', amount: 210_000_000 }),
    srp(4, { ship_type_id: 587, ship_name: 'Rifter', ship_type: 'Frigate', amount: 0, comments: 'Value not in the price table yet' }),
    srp(5, { character_id: 2112954543, character_name: 'Rens Alt', primary_character_id: 2112954540, primary_character_name: 'Hek Roamer', ship_type_id: 622, ship_name: 'Stabber', ship_type: 'Cruiser', amount: 24_500_000 }),
]

export const srp_edge: SRPUI[] = [
    srp(6, { is_corp_ship: true, character_id: 2112954544, character_name: 'Corp Hauler Pilot', primary_character_id: 2112954544, primary_character_name: 'Corp Hauler Pilot', ship_type_id: 28665, ship_name: 'Vargur', ship_type: 'Marauder', category: 'capital', amount: 1_450_000_000 }),
    srp(7, { fleet_id: 0, not_tracked_in_fleet: true, character_name: 'Bartholomew-Alexander of the Heimatar Highlands the Third', primary_character_name: 'Bartholomew-Alexander of the Heimatar Highlands the Third' }),
]

export const srp_busy: SRPUI[] = Array.from({ length: 16 }, (_, index) => srp(100 + index, {
    character_id: 2112970000 + index,
    character_name: `Fleet Pilot ${index + 1}`,
    primary_character_id: 2112970000 + index,
    primary_character_name: `Fleet Pilot ${index + 1}`,
    ship_type_id: index % 2 === 0 ? 24702 : 12015,
    ship_name: index % 2 === 0 ? 'Hurricane' : 'Muninn',
    ship_type: index % 2 === 0 ? 'Combat Battlecruiser' : 'Heavy Assault Cruiser',
    amount: 60_000_000 + index * 4_000_000,
}))

// --- Candidate fleets and combat logs ----------------------------------------------------

export const candidate_fleet: CandidateFleet = {
    id: 9390,
    type: 'strategic',
    objective: 'Amamake gate camp. Bring the Hurricane Brawl fit.',
    start_time: '2026-11-14T19:00:00Z',
    fleet_commander: {
        character_id: FCS.keldar.id,
        character_name: FCS.keldar.name,
        corporation_id: FCS.keldar.corporation_id,
        corporation_name: FCS.keldar.corporation_name,
    },
}

export const combat_log: FleetCombatLog = {
    id: 5501,
    uploaded_at: new Date('2026-11-14T22:10:00Z'),
    user_id: 3,
    logger: { character_id: FCS.tarsus.id, character_name: FCS.tarsus.name },
    character_name: 'Tarsus Rennir',
    system_name: 'Amamake',
}

/** The same candidate fleet with another type, objective or FC, for the card's variants. */
export const candidate_fleet_training: CandidateFleet = { ...candidate_fleet, id: 9392, type: 'training', objective: 'Frigate academy run, all welcome.' }
export const candidate_fleet_no_objective: CandidateFleet = { ...candidate_fleet, id: 9394, objective: '' }
export const candidate_fleet_long_fc: CandidateFleet = {
    ...candidate_fleet,
    id: 9395,
    fleet_commander: { ...candidate_fleet.fleet_commander, character_id: FCS.long_one.id, character_name: FCS.long_one.name, corporation_name: FCS.long_one.corporation_name },
}

/** A log uploaded without a character or system attached: the card drops its "On ..." line. */
export const combat_log_unattributed: FleetCombatLog = { ...combat_log, id: 5502, character_name: '', system_name: '' }
export const combat_log_long_name: FleetCombatLog = {
    ...combat_log,
    id: 5503,
    logger: { character_id: FCS.long_one.id, character_name: FCS.long_one.name },
    character_name: 'Bartholomew-Alexander of the Heimatar Highlands the Third',
    system_name: 'Old Man Star',
}

// --- Battle report pilot rows --------------------------------------------------------------

const HURRICANE_KILL = 134510244
const MUNINN_KILL = 134510250
const POD_KILL = 134510260

/** A pilot on a battle report side. Damage, share, loss and kills are the strings the report formats. */
const battle_pilot = (overrides: Partial<BattlePilotRow>): BattlePilotRow => ({
    character_id: FCS.keldar.id,
    name: FCS.keldar.name,
    icon_type_id: 24702,
    ship: 'Hurricane',
    killmail_id: null,
    pod_killmail_id: null,
    pod_title: '',
    lost: false,
    loss: '—',
    loss_note: '',
    damage: '1,240,000',
    share: '34%',
    damage_top: false,
    kills: 3,
    kills_top: false,
    corporation_id: CORPS.a_rat.corporation_id,
    corporation_name: CORPS.a_rat.corporation_name,
    alliance_id: 99011978,
    alliance_name: 'Minmatar Fleet Alliance',
    extras: [],
    ...overrides,
})

export const battle_pilot_survivor: BattlePilotRow = battle_pilot({
    character_id: FCS.vaenne.id,
    name: FCS.vaenne.name,
    icon_type_id: 11978,
    ship: 'Scimitar',
    damage: '640,000',
    share: '18%',
    kills: 1,
    corporation_id: CORPS.fosfo.corporation_id,
    corporation_name: CORPS.fosfo.corporation_name,
    alliance_id: null,
    alliance_name: '',
})

export const battle_pilot_lost: BattlePilotRow = battle_pilot({
    killmail_id: HURRICANE_KILL,
    lost: true,
    loss: '18,400,000 ISK',
    damage_top: true,
})

export const battle_pilot_multi_hull: BattlePilotRow = battle_pilot({
    character_id: FCS.tarsus.id,
    name: FCS.tarsus.name,
    icon_type_id: 622,
    ship: 'Stabber',
    killmail_id: 134510252,
    pod_killmail_id: POD_KILL,
    pod_title: 'Capsule lost',
    lost: true,
    loss: '31,000,000 ISK',
    loss_note: '2 hulls',
    kills: 6,
    kills_top: true,
    corporation_id: CORPS.tdt.corporation_id,
    corporation_name: CORPS.tdt.corporation_name,
    extras: [
        { type_id: 12015, title: 'Muninn, lost', lost: true, killmail_id: MUNINN_KILL },
        { type_id: 11978, title: 'Scimitar, survived', lost: false, killmail_id: null },
    ],
})

export const battle_pilot_no_icon: BattlePilotRow = battle_pilot({
    character_id: FCS.ilsa.id,
    name: FCS.ilsa.name,
    icon_type_id: null,
    ship: 'Unknown hull',
    damage: '0',
    share: '0%',
    kills: 0,
    corporation_id: null,
    corporation_name: '',
    alliance_id: null,
    alliance_name: '',
})

export const battle_pilot_long_name: BattlePilotRow = battle_pilot({
    character_id: FCS.long_one.id,
    name: FCS.long_one.name,
    ship: 'Hurricane Fleet Issue',
    killmail_id: HURRICANE_KILL,
    lost: true,
    loss: '205,000,000 ISK',
    corporation_name: 'Fraternity of the Old Spice Frigate Order',
    corporation_id: CORPS.fosfo.corporation_id,
    alliance_name: 'Minmatar Fleet Alliance',
})

// Mining fleets (docs/fleets/mining-tracking.md): a 90-minute fleet in six
// 15-minute buckets. Alex mines throughout; Taylor idles for 30 minutes; a
// multiboxer's two characters leave together after an hour; Pat has no
// mining scope.
const MINING_START = Date.UTC(2026, 10, 22, 18, 0)
const mining_at = (minutes: number) => new Date(MINING_START + minutes * 60_000).toISOString()

const mining_pilot = (
    character_id: number | null,
    character_name: string | null,
    cells: FleetMiningTimeline['pilots'][number]['cells'],
    cell_m3: number[],
    no_scope = false,
): FleetMiningTimeline['pilots'][number] => {
    const in_fleet = cells.filter(c => c !== 'out').length
    const with_ore = cells.filter(c => c === 'ore').length
    return {
        character_id,
        character_name,
        no_scope,
        cells,
        cell_m3,
        volume_m3: cell_m3.reduce((a, b) => a + b, 0),
        mining_pct: no_scope || !in_fleet ? null : Math.round(100 * with_ore / in_fleet),
    }
}

const mining_event = (minutes: number, kind: FleetMiningEvent['kind'], name: string, extra: Partial<FleetMiningEvent> = {}): FleetMiningEvent => ({
    at: mining_at(minutes),
    kind,
    character_id: null,
    character_name: name,
    type_id: null,
    ore_name: null,
    quantity: null,
    volume_m3: null,
    ...extra,
})

const MINING_PILOTS = [
    mining_pilot(95000001, 'Alex Example', ['ore', 'ore', 'ore', 'ore', 'ore', 'ore'], [6000, 6200, 5800, 6100, 6000, 5900]),
    mining_pilot(95000002, 'Taylor Trial', ['ore', 'idle', 'idle', 'ore', 'ore', 'quiet'], [2400, 0, 0, 2500, 2300, 0]),
    mining_pilot(95000003, 'Boxer Main', ['ore', 'ore', 'ore', 'ore', 'out', 'out'], [1500, 1500, 1500, 1500, 0, 0]),
    mining_pilot(95000004, 'Boxer Alt One', ['ore', 'ore', 'ore', 'ore', 'out', 'out'], [1500, 1500, 1500, 1500, 0, 0]),
    mining_pilot(95000005, 'Pat Noscope', ['quiet', 'quiet', 'quiet', 'quiet', 'quiet', 'quiet'], [0, 0, 0, 0, 0, 0], true),
]

export const mining_timeline: FleetMiningTimeline = {
    bucket_minutes: 15,
    start: mining_at(0),
    end: mining_at(90),
    buckets: [0, 15, 30, 45, 60, 75].map(mining_at),
    totals_m3: [0, 1, 2, 3, 4, 5].map(i => MINING_PILOTS.reduce((sum, p) => sum + p.cell_m3[i], 0)),
    pilots: MINING_PILOTS,
    events: [
        mining_event(74, 'ore', 'Alex Example', { type_id: 1230, ore_name: 'Veldspar', quantity: 59000, volume_m3: 5900 }),
        mining_event(60, 'leave', 'Boxer Alt One'),
        mining_event(60, 'leave', 'Boxer Main'),
        mining_event(59, 'ore', 'Taylor Trial', { type_id: 1228, ore_name: 'Scordite', quantity: 15333, volume_m3: 2300 }),
        mining_event(0, 'join', 'Alex Example'),
    ],
}

const mining_ore = (type_id: number, name: string, quantity: number, volume_m3: number, isk_estimate: number) =>
    ({ type_id, name, quantity, volume_m3, isk_estimate })

export const mining_fleet: FleetMining = {
    track_mining: true,
    measuring: false,
    updated_at: mining_at(101),
    pilots: [
        { character_id: 95000001, character_name: 'Alex Example', status: 'done', ores: [mining_ore(1230, 'Veldspar', 360000, 36000, 3780000)], volume_m3: 36000, isk_estimate: 3780000 },
        { character_id: 95000002, character_name: 'Taylor Trial', status: 'done', ores: [mining_ore(1228, 'Scordite', 48000, 7200, 806000)], volume_m3: 7200, isk_estimate: 806000 },
        { character_id: 95000003, character_name: 'Boxer Main', status: 'done', ores: [mining_ore(1230, 'Veldspar', 60000, 6000, 630000)], volume_m3: 6000, isk_estimate: 630000 },
        { character_id: 95000004, character_name: 'Boxer Alt One', status: 'done', ores: [mining_ore(1230, 'Veldspar', 60000, 6000, 630000)], volume_m3: 6000, isk_estimate: 630000 },
        { character_id: 95000005, character_name: 'Pat Noscope', status: 'no_scope', ores: [], volume_m3: 0, isk_estimate: 0 },
    ],
    ores: [mining_ore(1230, 'Veldspar', 480000, 48000, 5040000), mining_ore(1228, 'Scordite', 48000, 7200, 806000)],
    volume_m3: 55200,
    isk_estimate: 5846000,
    pilots_no_scope: 1,
    timeline: mining_timeline,
}

export const mining_fleet_no_timeline: FleetMining = { ...mining_fleet, timeline: null, measuring: true }
