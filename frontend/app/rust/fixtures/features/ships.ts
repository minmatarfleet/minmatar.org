// Fixtures for the Features/Ships stories: fittings, doctrines, skillsets, the Training tab and SRP killmail analysis.
// Ship and module ids and names come from rust/fixtures/sde.json; pilots and corps from rust/stories/_controls.ts.
import type {
    CargoItem,
    Damage,
    DoctrineLocationUI,
    DoctrineType,
    FittingGroup,
    FittingItem,
    KillmailAnalysis,
    Module,
    ShipFitting,
    Skillset,
    CharacterBasic,
    SkillsetMissingSkillUI,
} from '@dtypes/layout_components'
import type { SummaryCharacter, TrainingBring, TrainingCharacterSummary, TrainingOverview } from '@dtypes/api.minmatar.org'

// ---------------------------------------------------------------------------------------------------------------
// Fittings
// ---------------------------------------------------------------------------------------------------------------

const eft = (hull: string, name: string, lines: string[]) => `[${hull}, ${name}]\n\n${lines.join('\n')}`

export const rifter_fitting: FittingItem = {
    id: 1201,
    fitting_name: 'Rifter - Amamake Brawler',
    fitting_type: 'Primary',
    tags: ['nanogang', 'new_player_friendly'],
    ship_type: 'Frigate',
    ship_name: 'Rifter',
    ship_id: 587,
    ship_meta: 'Tech I',
    eft_format: eft('Rifter', 'Rifter - Amamake Brawler', [
        '200mm AutoCannon II, Republic Fleet Phased Plasma S',
        '200mm AutoCannon II, Republic Fleet Phased Plasma S',
        '200mm AutoCannon II, Republic Fleet Phased Plasma S',
        '',
        '5MN Microwarpdrive II',
        'Warp Scrambler II',
        '',
        'Gyrostabilizer II',
        'Gyrostabilizer II',
        'Damage Control II',
    ]),
}

export const stabber_fitting: FittingItem = {
    id: 1202,
    fitting_name: 'Stabber - Kite',
    fitting_type: 'Primary',
    tags: ['nanogang', 'faction_warfare'],
    ship_type: 'Cruiser',
    ship_name: 'Stabber',
    ship_id: 622,
    ship_meta: 'Tech I',
    eft_format: eft('Stabber', 'Stabber - Kite', [
        '720mm Howitzer Artillery II, Republic Fleet Phased Plasma M',
        '720mm Howitzer Artillery II, Republic Fleet Phased Plasma M',
        '720mm Howitzer Artillery II, Republic Fleet Phased Plasma M',
        '',
        '10MN Afterburner II',
        'Warp Scrambler II',
        '',
        'Gyrostabilizer II',
        'Damage Control II',
    ]),
}

export const hurricane_fitting: FittingItem = {
    id: 1203,
    fitting_name: 'Hurricane - Autocannon Fleet',
    fitting_type: 'Primary',
    tags: ['fleet_composition', 'nullsec'],
    ship_type: 'Battlecruiser',
    ship_name: 'Hurricane',
    ship_id: 24702,
    ship_meta: 'Tech I',
    eft_format: eft('Hurricane', 'Hurricane - Autocannon Fleet', [
        '720mm Howitzer Artillery II, Republic Fleet Phased Plasma L',
        '',
        '50MN Microwarpdrive II',
        'Warp Scrambler II',
        '',
        'Gyrostabilizer II',
        'Gyrostabilizer II',
        'Damage Control II',
    ]),
}

export const vagabond_fitting: FittingItem = {
    id: 1204,
    fitting_name: 'Vagabond - Fast Pursuit',
    fitting_type: 'Support',
    tags: ['nullsec'],
    ship_type: 'Heavy Assault Cruiser',
    ship_name: 'Vagabond',
    ship_id: 11999,
    ship_meta: 'Tech II',
    eft_format: eft('Vagabond', 'Vagabond - Fast Pursuit', [
        '425mm AutoCannon II, Republic Fleet Phased Plasma M',
        '',
        '10MN Microwarpdrive II',
        'Warp Scrambler II',
        '',
        'Gyrostabilizer II',
    ]),
}

export const svipul_fitting: FittingItem = {
    id: 1205,
    fitting_name: 'Svipul - Tackle Destroyer',
    fitting_type: 'Support',
    tags: ['escape_frigate'],
    ship_type: 'Tactical Destroyer',
    ship_name: 'Svipul',
    ship_id: 34562,
    ship_meta: 'Tech III',
    eft_format: eft('Svipul', 'Svipul - Tackle Destroyer', [
        '200mm AutoCannon II, Republic Fleet Phased Plasma S',
        '',
        '5MN Microwarpdrive II',
        'Warp Scrambler II',
    ]),
}

export const cynabal_fitting: FittingItem = {
    id: 1206,
    fitting_name: 'Cynabal - Raiding Party',
    fitting_type: 'Utility',
    tags: ['faction_warfare', 'nanogang'],
    ship_type: 'Cruiser',
    ship_name: 'Cynabal',
    ship_id: 17720,
    ship_meta: 'Faction',
    eft_format: eft('Cynabal', 'Cynabal - Raiding Party', [
        '425mm AutoCannon II, Republic Fleet Phased Plasma M',
        '',
        '50MN Microwarpdrive II',
        'Warp Scrambler II',
    ]),
}

export const scimitar_fitting: FittingItem = {
    id: 1207,
    fitting_name: 'Scimitar - Shield Logistics',
    fitting_type: 'Support',
    tags: ['fleet_composition'],
    ship_type: 'Logistics',
    ship_name: 'Scimitar',
    ship_id: 11978,
    ship_meta: 'Tech II',
    eft_format: eft('Scimitar', 'Scimitar - Shield Logistics', [
        'Medium Remote Shield Booster II',
        '',
        '10MN Microwarpdrive II',
        'Warp Scrambler II',
    ]),
}

export const vargur_fitting: FittingItem = {
    id: 1208,
    fitting_name: 'Vargur - Long Range Artillery',
    fitting_type: 'Capital',
    tags: ['capitals', 'fleet_composition'],
    ship_type: 'Marauder',
    ship_name: 'Vargur',
    ship_id: 28665,
    ship_meta: 'Tech II',
    eft_format: eft('Vargur', 'Vargur - Long Range Artillery', [
        '720mm Howitzer Artillery II, Republic Fleet Phased Plasma L',
        '',
        '500MN Microwarpdrive II',
    ]),
}

export const hurricane_fleet_issue_fitting: FittingItem = {
    id: 1209,
    fitting_name: 'Hurricane Fleet Issue - Alpha Strike',
    fitting_type: 'Primary',
    tags: ['fleet_composition', 'command_bursts'],
    ship_type: 'Battlecruiser',
    ship_name: 'Hurricane Fleet Issue',
    ship_id: 33157,
    ship_meta: 'Faction',
    eft_format: eft('Hurricane Fleet Issue', 'Hurricane Fleet Issue - Alpha Strike', [
        '720mm Howitzer Artillery II, Republic Fleet Phased Plasma L',
        '',
        '50MN Microwarpdrive II',
        'Warp Scrambler II',
    ]),
}

/** Fitting with no tags, no meta and a very long name. */
export const long_name_fitting: FittingItem = {
    id: 1290,
    fitting_name: 'Rifter - Amamake Gate Camp Brawler (Shield Tank, Scrambler, Light Neutron Blaster Swap) [Alts Welcome] v14',
    fitting_type: 'Alts',
    ship_type: 'Frigate',
    ship_name: 'Rifter',
    ship_id: 587,
    eft_format: eft('Rifter', 'Rifter - Amamake Gate Camp Brawler', ['200mm AutoCannon II', '', '5MN Microwarpdrive II']),
}

/** A page's "ship fittings grid": every ship, every kind of meta group. */
export const fittings_busy: FittingItem[] = [
    rifter_fitting, stabber_fitting, hurricane_fitting, vagabond_fitting, svipul_fitting, cynabal_fitting,
    scimitar_fitting, vargur_fitting, hurricane_fleet_issue_fitting, long_name_fitting,
]

// ---------------------------------------------------------------------------------------------------------------
// Doctrines
// ---------------------------------------------------------------------------------------------------------------

const when = new Date('2026-10-14T18:00:00Z')

export const AMAMAKE_LOCATION_ID = 60003760

const doctrine = (overrides: Partial<DoctrineType> & Pick<DoctrineType, 'id' | 'name' | 'type' | 'primary_fittings'>): DoctrineType => ({
    created_at: when,
    updated_at: when,
    description: '',
    secondary_fittings: [],
    support_fittings: [],
    utility_fittings: [],
    alts_fittings: [],
    capitals_fittings: [],
    location_ids: [AMAMAKE_LOCATION_ID],
    ...overrides,
})

export const doctrine_hurricane_strategic: DoctrineType = doctrine({
    id: 31,
    name: 'Hurricane Autocannon Fleet',
    type: 'strategic',
    description: 'Our standing strategic doctrine for Amamake defence: Hurricanes at the front, Scimitars behind them and a Vagabond screen for pursuit. Bring a spare Rifter for the gate.',
    primary_fittings: [hurricane_fitting, hurricane_fleet_issue_fitting],
    support_fittings: [scimitar_fitting, vagabond_fitting],
    utility_fittings: [svipul_fitting],
    location_ids: [AMAMAKE_LOCATION_ID, 60004588],
})

export const doctrine_rifter_nonstrategic: DoctrineType = doctrine({
    id: 12,
    name: 'Rifter Frigate Roam',
    type: 'non_strategic',
    description: 'Cheap, fast and expendable. A roaming doctrine for new pilots; every fit is covered by SRP.',
    primary_fittings: [rifter_fitting],
    alts_fittings: [long_name_fitting],
})

export const doctrine_stabber_nonstrategic: DoctrineType = doctrine({
    id: 14,
    name: 'Stabber Kite',
    type: 'non_strategic',
    description: 'Artillery kiting cruisers.',
    primary_fittings: [stabber_fitting],
    secondary_fittings: [cynabal_fitting],
})

export const doctrine_vargur_capital: DoctrineType = doctrine({
    id: 40,
    name: 'Vargur Hammer',
    type: 'capital',
    description: 'Marauders for the strategic capital timer. Needs L3 fleet approval.',
    primary_fittings: [vargur_fitting],
    capitals_fittings: [vargur_fitting],
    location_ids: [60004588],
})

export const doctrine_svipul_experimental: DoctrineType = doctrine({
    id: 51,
    name: 'Svipul Skirmish Trial',
    type: 'experimental',
    description: 'A trial doctrine: three Svipuls and a Cynabal try to hold a gate against bigger hulls.',
    primary_fittings: [svipul_fitting, cynabal_fitting],
    location_ids: [AMAMAKE_LOCATION_ID, 60004588, 60008494],
})

/** A doctrine with every tier filled in. */
export const doctrine_full: DoctrineType = {
    ...doctrine_hurricane_strategic,
    secondary_fittings: [cynabal_fitting],
    alts_fittings: [long_name_fitting],
    capitals_fittings: [vargur_fitting],
}

/** A doctrine whose lone primary ship is long-named, single-location. */
export const doctrine_long_name: DoctrineType = doctrine({
    id: 77,
    name: 'Rifter Amamake Gate Camp Brawler Doctrine for Alliance Alts and New Pilots (Strategic Refit)',
    type: 'non_strategic',
    description: 'Edge case: a doctrine name far longer than its card.',
    primary_fittings: [long_name_fitting],
})

export const amamake_doctrines: DoctrineType[] = [
    doctrine_hurricane_strategic,
    doctrine_rifter_nonstrategic,
    doctrine_stabber_nonstrategic,
    doctrine_svipul_experimental,
]

export const doctrine_location_amamake: DoctrineLocationUI = {
    id: AMAMAKE_LOCATION_ID,
    name: 'Amamake - 5 times nearly AT winners',
    doctrine_count: amamake_doctrines.length,
    doctrines: amamake_doctrines,
}

export const doctrine_location_rens: DoctrineLocationUI = {
    id: 60004588,
    name: 'Rens VI - Moon 8 - Brutor Tribe Treasury',
    doctrine_count: 2,
    doctrines: [doctrine_vargur_capital, doctrine_svipul_experimental],
}

export const doctrine_location_auga: DoctrineLocationUI = {
    id: 60008494,
    name: 'Auga VI - Moon 1 - Republic Fleet Assembly Plant',
    doctrine_count: 1,
    doctrines: [doctrine_svipul_experimental],
}

export const doctrine_location_all: DoctrineLocationUI = {
    id: 0,
    name: 'All locations',
    doctrine_count: 6,
    doctrines: [...amamake_doctrines, doctrine_vargur_capital, doctrine_long_name],
}

export const doctrine_location_empty: DoctrineLocationUI = {
    id: 60008494,
    name: 'Auga VI - Moon 1 - Republic Fleet Assembly Plant',
    doctrine_count: 0,
    doctrines: [],
}

// ---------------------------------------------------------------------------------------------------------------
// Fit view: slots, modules and cargo
// ---------------------------------------------------------------------------------------------------------------

const module = (id: number, name: string, meta_name: Module['meta_name'], module_type: string, slot_name: string): Module => ({
    id, name, meta_name, module_type, slot_name,
})

export const autocannon_t2 = module(2889, '200mm AutoCannon II', 'Tech II', 'Projectile Weapon', 'High Slots')
export const autocannon_t1 = module(486, '200mm AutoCannon I', 'Tech I', 'Projectile Weapon', 'High Slots')
export const autocannon_faction = module(16050, 'Republic Fleet 200mm Autocannon', 'Faction', 'Projectile Weapon', 'High Slots')
export const autocannon_officer = module(85010, "Ramaku's Modified 200mm AutoCannon", 'Officer', 'Projectile Weapon', 'High Slots')
export const mwd_t2 = module(440, '5MN Microwarpdrive II', 'Tech II', 'Propulsion Module', 'Medium Slots')
export const mwd_deadspace = module(19343, 'Gistii B-Type 5MN Microwarpdrive', 'Deadspace', 'Propulsion Module', 'Medium Slots')
export const scram_t2 = module(448, 'Warp Scrambler II', 'Tech II', 'Warp Scrambler', 'Medium Slots')
export const scram_faction = module(14254, 'Domination Warp Scrambler', 'Faction', 'Warp Scrambler', 'Medium Slots')
export const scram_storyline = module(21512, "'Delineative' Warp Scrambler", 'Storyline', 'Warp Scrambler', 'Medium Slots')
export const gyro_t2 = module(519, 'Gyrostabilizer II', 'Tech II', 'Gyrostabilizer', 'Low Slots')
export const gyro_storyline = module(21486, "'Kindred' Gyrostabilizer", 'Storyline', 'Gyrostabilizer', 'Low Slots')
export const damage_control_t2 = module(2048, 'Damage Control II', 'Tech II', 'Damage Control', 'Low Slots')

/** The Rifter's ship_slot/slot_type pairs, as the fitting pages feed them to FittingSlot. */
export const rifter_ship_fitting: ShipFitting = {
    name: 'Rifter - Amamake Brawler',
    ship_name: 'Rifter',
    capabilities: { high_slots: 3, med_slots: 3, low_slots: 4, rig_slots: 3, turrets: 3, launchers: 2 },
    high_slots: [autocannon_t2, autocannon_t2, autocannon_faction],
    med_slots: [mwd_t2, scram_t2],
    low_slots: [gyro_t2, gyro_t2, damage_control_t2],
    rig_slots: [],
    drones: [],
    cargohold: [{ id: 2889, name: '200mm AutoCannon II', amount: 1 }],
}

/** The Fit block's groups: a named list of modules per slot kind, including amounts and a skipped empty group. */
export const rifter_fit_groups: FittingGroup[] = [
    {
        name: 'High Slots',
        modules: [
            { id: 2889, name: '200mm AutoCannon II' },
            { id: 2889, name: '200mm AutoCannon II' },
            { id: 16050, name: 'Republic Fleet 200mm Autocannon' },
        ],
    },
    {
        name: 'Medium Slots',
        modules: [
            { id: 440, name: '5MN Microwarpdrive II' },
            { id: 448, name: 'Warp Scrambler II' },
        ],
    },
    {
        name: 'Low Slots',
        modules: [
            { id: 519, name: 'Gyrostabilizer II', amount: 2 },
            { id: 2048, name: 'Damage Control II' },
        ],
    },
    { name: 'Rig Slots', modules: [] },
    {
        name: 'Cargo',
        modules: [
            { id: 2889, name: '200mm AutoCannon II', amount: 2 },
        ] satisfies CargoItem[],
    },
]

// ---------------------------------------------------------------------------------------------------------------
// Skillsets
// ---------------------------------------------------------------------------------------------------------------

export const skillset_pilot: CharacterBasic = {
    character_id: 2112954532,
    character_name: "Kel'dar Atram",
    corporation: undefined,
}

export const skillsets_busy: Skillset[] = [
    {
        name: 'Academy Starter Plan',
        progress: 100,
        missing_skills: [],
    },
    {
        name: 'Magic 14',
        progress: 64,
        missing_skills: [
            { skill_name: 'Gunnery', skill_level: 4 },
            { skill_name: 'Small Projectile Turret', skill_level: 5 },
            { skill_name: 'Navigation', skill_level: 4 },
        ],
    },
    {
        name: 'Shield Logistics Cruisers',
        progress: 38,
        missing_skills: [
            { skill_name: 'Logistics Cruisers', skill_level: 3 },
            { skill_name: 'Shield Emission Systems', skill_level: 5 },
            { skill_name: 'Remote Shield Emission', skill_level: 4 },
        ],
    },
    {
        name: 'Armor Logistics Cruisers',
        progress: 12,
        missing_skills: [
            { skill_name: 'Logistics Cruisers', skill_level: 5 },
            { skill_name: 'Remote Armor Repair Systems', skill_level: 5 },
        ],
    },
    {
        name: 'Revelation/RNI',
        progress: 3,
        missing_skills: [
            { skill_name: 'Capital Ships', skill_level: 5 },
            { skill_name: 'Dreadnought Operation', skill_level: 3 },
        ],
    },
    {
        name: 'Hurricane Fleet Issue Brawler (Armor, Heavy Neutron Blaster Refit, Alts Welcome)',
        progress: 91,
        missing_skills: [{ skill_name: 'Medium Projectile Turret', skill_level: 5 }],
    },
]

export const skillsets_only_new_player: Skillset[] = skillsets_busy.slice(0, 2)

export const missing_skills_partial: SkillsetMissingSkillUI = {
    skillsets: skillsets_busy[1],
    character: skillset_pilot,
}

export const missing_skills_with_repeats: SkillsetMissingSkillUI = {
    skillsets: {
        name: 'Shield Logistics Cruisers',
        progress: 22,
        missing_skills: [
            { skill_name: 'Logistics Cruisers', skill_level: 1 },
            { skill_name: 'Logistics Cruisers', skill_level: 2 },
            { skill_name: 'Logistics Cruisers', skill_level: 3 },
            { skill_name: 'Shield Emission Systems', skill_level: 5 },
            { skill_name: 'Remote Shield Emission', skill_level: 4 },
        ],
    },
    character: skillset_pilot,
}

export const missing_skills_none: SkillsetMissingSkillUI = {
    skillsets: { name: 'Academy Starter Plan', progress: 100, missing_skills: [] },
    character: skillset_pilot,
}

export const account_characters: SummaryCharacter[] = [
    { character_id: 2112954532, character_name: "Kel'dar Atram", is_primary: true, corp_id: 98726134, corp_name: 'Rattini Tribe', alliance_id: 99011978, alliance_name: 'Minmatar Fleet Alliance', esi_token: null, flags: [], token_status: 'valid' },
    { character_id: 2112954533, character_name: 'Rattini Pilot', is_primary: false, corp_id: 98726134, corp_name: 'Rattini Tribe', alliance_id: 99011978, alliance_name: 'Minmatar Fleet Alliance', esi_token: null, flags: [], token_status: 'valid' },
    { character_id: 2112954534, character_name: 'Hek Roamer', is_primary: false, corp_id: 98726134, corp_name: 'Rattini Tribe', alliance_id: 99011978, alliance_name: 'Minmatar Fleet Alliance', esi_token: null, flags: [], token_status: 'valid' },
]

// ---------------------------------------------------------------------------------------------------------------
// Training tab
// ---------------------------------------------------------------------------------------------------------------

type Ship = TrainingCharacterSummary['ready'][number]

const ship = (fitting_id: number, name: string, ship_type_id: number, capability: string, doctrines: string[]): Ship => ({
    fitting_id, name, ship_type_id, capability, doctrines,
})

const ready_rifter = ship(1201, 'Rifter - Amamake Brawler', 587, 'frontline', ['Rifter Frigate Roam'])
const ready_stabber = ship(1202, 'Stabber - Kite', 622, 'frontline', ['Stabber Kite'])
const ready_hurricane = ship(1203, 'Hurricane - Autocannon Fleet', 24702, 'frontline', ['Hurricane Autocannon Fleet'])
const ready_vagabond = ship(1204, 'Vagabond - Fast Pursuit', 11999, 'tackle', ['Hurricane Autocannon Fleet'])
const ready_svipul = ship(1205, 'Svipul - Tackle Destroyer', 34562, 'tackle', ['Svipul Skirmish Trial'])
const ready_cynabal = ship(1206, 'Cynabal - Raiding Party', 17720, 'tackle', ['Svipul Skirmish Trial'])
const ready_scimitar = ship(1207, 'Scimitar - Shield Logistics', 11978, 'logistics', ['Hurricane Autocannon Fleet'])
const ready_cyclone = ship(1210, 'Cyclone - Missile Brawler', 16231, 'frontline', ['Hurricane Autocannon Fleet'])
const ready_thrasher = ship(1211, 'Thrasher - Alpha', 16242, 'frontline', ['Rifter Frigate Roam'])

const character = (overrides: Partial<TrainingCharacterSummary> & Pick<TrainingCharacterSummary, 'character_id' | 'name'>): TrainingCharacterSummary => ({
    skill_points: 58_000_000,
    account: 1,
    not_for_fleets: false,
    goals: [],
    goals_ready: 0,
    all_done: false,
    training: null,
    queued: [],
    ready: [],
    suggestions: [],
    nothing_close: false,
    ...overrides,
})

const goal_scimitar = {
    fitting_id: 1207,
    name: 'Scimitar - Shield Logistics',
    ship_type_id: 11978,
    capability: 'logistics',
    doctrines: ['Hurricane Autocannon Fleet'],
    ready: false,
    done: false,
    unlocked: true,
    days: 3.4,
    skills: 7,
    target: 'Logistics Cruisers V',
}

const goal_vagabond = {
    fitting_id: 1204,
    name: 'Vagabond - Fast Pursuit',
    ship_type_id: 11999,
    capability: 'tackle',
    doctrines: ['Hurricane Autocannon Fleet'],
    ready: true,
    done: true,
    unlocked: true,
    days: 0,
    skills: 0,
    target: 'Heavy Assault Cruisers IV',
}

/** Main: five ships ready, two goals, one in training. */
export const training_main = character({
    character_id: 2112954532,
    name: "Kel'dar Atram",
    skill_points: 94_300_000,
    goals: [goal_vagabond, goal_scimitar],
    goals_ready: 1,
    training: goal_scimitar,
    ready: [ready_rifter, ready_stabber, ready_hurricane, ready_vagabond, ready_svipul],
})

/** Alt: ready in eight ships so the row shows the "+N" chip. */
export const training_alt_many_ready = character({
    character_id: 2112954533,
    name: 'Rattini Pilot',
    skill_points: 41_800_000,
    goals: [goal_vagabond],
    goals_ready: 1,
    all_done: true,
    ready: [ready_rifter, ready_stabber, ready_hurricane, ready_vagabond, ready_svipul, ready_cynabal, ready_scimitar, ready_cyclone],
})

/** Fresh character: nothing ready, nothing in training. */
export const training_new = character({
    character_id: 2112954534,
    name: 'Hek Roamer',
    skill_points: 4_200_000,
    ready: [],
})

export const training_not_for_fleets = character({
    character_id: 2112954535,
    name: 'Amamake Hauler',
    skill_points: 12_600_000,
    not_for_fleets: true,
    ready: [ready_thrasher],
})

export const training_long_name = character({
    character_id: 2112954536,
    name: "Alexandria 'The Frigate Whisperer' Rattini-Brutor of the Seventh Tribe",
    skill_points: 820_000,
    goals: [{ ...goal_scimitar, name: 'Scimitar - Shield Logistics (Remote Booster Heavy, Cap Stable, Alts Welcome v3)', days: 0.02 }],
    goals_ready: 0,
    training: { ...goal_scimitar, name: 'Scimitar - Shield Logistics (Remote Booster Heavy, Cap Stable, Alts Welcome v3)', days: 0.02 },
    ready: [ready_rifter],
})

export const training_bring_one_seat: TrainingBring = {
    academy: false,
    seats: 1,
    columns: ['Frontline', 'Tackle', 'Logistics'],
    doctrines: [
        {
            doctrine_id: 31, name: 'Hurricane Autocannon Fleet', strategic: true, ship_type_id: 24702, seats: 1,
            cells: [
                { column: 'Frontline', ships: 2, ready: 1, state: 'ready', seats: 1, days: 0 },
                { column: 'Tackle', ships: 1, ready: 1, state: 'ready', seats: 1, days: 0 },
                { column: 'Logistics', ships: 1, ready: 0, state: 'training', seats: 0, days: 3.4 },
            ],
        },
        {
            doctrine_id: 12, name: 'Rifter Frigate Roam', strategic: false, ship_type_id: 587, seats: 1,
            cells: [
                { column: 'Frontline', ships: 1, ready: 1, state: 'ready', seats: 1, days: 0 },
                { column: 'Tackle', ships: 0, ready: 0, state: 'none', seats: 0, days: null },
                { column: 'Logistics', ships: 0, ready: 0, state: 'none', seats: 0, days: null },
            ],
        },
    ],
}

export const training_bring_multi_seat: TrainingBring = {
    academy: false,
    seats: 3,
    columns: ['Frontline', 'Tackle', 'Logistics', 'Utility'],
    doctrines: [
        {
            doctrine_id: 31, name: 'Hurricane Autocannon Fleet', strategic: true, ship_type_id: 24702, seats: 3,
            cells: [
                { column: 'Frontline', ships: 3, ready: 3, state: 'ready', seats: 3, days: 0 },
                { column: 'Tackle', ships: 1, ready: 2, state: 'ready', seats: 2, days: 0 },
                { column: 'Logistics', ships: 1, ready: 0, state: 'training', seats: 0, days: 0.4 },
                { column: 'Utility', ships: 1, ready: 0, state: 'training', seats: 0, days: null },
            ],
        },
        {
            doctrine_id: 40, name: 'Vargur Hammer', strategic: true, ship_type_id: 28665, seats: 0,
            cells: [
                { column: 'Frontline', ships: 1, ready: 0, state: 'training', seats: 0, days: 41 },
                { column: 'Tackle', ships: 0, ready: 0, state: 'none', seats: 0, days: null },
                { column: 'Logistics', ships: 0, ready: 0, state: 'none', seats: 0, days: null },
                { column: 'Utility', ships: 0, ready: 0, state: 'none', seats: 0, days: null },
            ],
        },
        {
            doctrine_id: 14, name: 'Stabber Kite', strategic: false, ship_type_id: 622, seats: 2,
            cells: [
                { column: 'Frontline', ships: 1, ready: 2, state: 'ready', seats: 2, days: 0 },
                { column: 'Tackle', ships: 1, ready: 1, state: 'ready', seats: 1, days: 0 },
                { column: 'Logistics', ships: 0, ready: 0, state: 'none', seats: 0, days: null },
                { column: 'Utility', ships: 0, ready: 0, state: 'none', seats: 0, days: null },
            ],
        },
    ],
}

export const training_bring_empty: TrainingBring = { academy: false, seats: 1, columns: [], doctrines: [] }

export const training_overview_typical: TrainingOverview = {
    accounts: [
        { number: 1, characters: [training_main, training_alt_many_ready, training_new] },
        { number: 2, characters: [training_not_for_fleets] },
    ],
    unplaced: [training_long_name],
    bring: training_bring_multi_seat,
}

export const training_overview_single_account: TrainingOverview = {
    accounts: [],
    unplaced: [training_main],
    bring: training_bring_one_seat,
}

export const training_overview_empty: TrainingOverview = {
    accounts: [],
    unplaced: [],
    bring: training_bring_empty,
}

// ---------------------------------------------------------------------------------------------------------------
// Killmail breakdown (SRP) and damage
// ---------------------------------------------------------------------------------------------------------------

export const killmail_rifter_loss: KillmailAnalysis = {
    ship_id: 587,
    ship_name: 'Rifter',
    character_id: 2112954532,
    character_name: "Kel'dar Atram",
    killmail_time: new Date('2026-10-14T19:42:11Z'),
    value: 18_400_000,
    program: 'subcapitals',
    candidate_fleets: [
        {
            id: 94,
            type: 'strategic',
            start_time: '2026-10-14T18:00:00Z',
            objective: 'Defend the Amamake TCU timer against the Stainwagon coalition.',
            fleet_commander: {
                character_id: 2112954533,
                character_name: 'Rattini Pilot',
                corporation_id: 98726134,
                corporation_name: 'Rattini Tribe',
            },
        },
        {
            id: 95,
            type: 'non_strategic',
            start_time: '2026-10-14T19:30:00Z',
            objective: 'Frigate roam through Auga and Hek.',
            fleet_commander: {
                character_id: 2112954534,
                character_name: 'Hek Roamer',
                corporation_id: 98726134,
                corporation_name: 'Rattini Tribe',
            },
        },
    ],
}

export const killmail_no_fleet: KillmailAnalysis = { ...killmail_rifter_loss, candidate_fleets: [] }
export const killmail_wrong_program: KillmailAnalysis = { ...killmail_rifter_loss, program: 'dreads' }
export const killmail_not_eligible: KillmailAnalysis = { ...killmail_rifter_loss, program: null, ship_id: 17812, ship_name: 'Republic Fleet Firetail', value: 41_900_000, candidate_fleets: [] }

export const damage_two_way: Damage = {
    name: 'Hurricane Fleet Issue',
    item_type: 33157,
    total_from: 48_210,
    dps_from: 1_340,
    volleys_from: 36,
    max_from: 2_900,
    total_to: 112_840,
    dps_to: 1_820,
    volleys_to: 62,
    max_to: 3_400,
}

export const damage_only_dealt: Damage = { ...damage_two_way, name: 'Stabber', item_type: 622, total_from: 0, dps_from: 0, volleys_from: 0, max_from: 0 }
export const damage_only_taken: Damage = { ...damage_two_way, name: 'Rifter', item_type: 587, total_to: 0, dps_to: 0, volleys_to: 0, max_to: 0 }
export const damage_none: Damage = { ...damage_two_way, name: 'Scimitar', item_type: 11978, total_to: 0, dps_to: 0, volleys_to: 0, max_to: 0, total_from: 0, dps_from: 0, volleys_from: 0, max_from: 0 }
export const damage_big: Damage = { ...damage_two_way, name: 'Vargur', item_type: 28665, total_to: 18_204_113, dps_to: 4_820, volleys_to: 3_776, total_from: 9_118_402, dps_from: 2_405, volleys_from: 3_791 }

// ---------------------------------------------------------------------------------------------------------------
// Useful-for ships
// ---------------------------------------------------------------------------------------------------------------

export const useful_for_few = [
    { ship_id: 587, fitting_name: 'Rifter - Amamake Brawler' },
    { ship_id: 622, fitting_name: 'Stabber - Kite' },
]

export const useful_for_many = [
    { ship_id: 587, fitting_name: 'Rifter - Amamake Brawler' },
    { ship_id: 622, fitting_name: 'Stabber - Kite' },
    { ship_id: 24702, fitting_name: 'Hurricane - Autocannon Fleet' },
    { ship_id: 11999, fitting_name: 'Vagabond - Fast Pursuit' },
    { ship_id: 34562, fitting_name: 'Svipul - Tackle Destroyer' },
    { ship_id: 17720, fitting_name: 'Cynabal - Raiding Party' },
    { ship_id: 11978, fitting_name: 'Scimitar - Shield Logistics' },
    { ship_id: 16231, fitting_name: 'Cyclone - Missile Brawler' },
    { ship_id: 16242, fitting_name: 'Thrasher - Alpha' },
    { ship_id: 598, fitting_name: 'Breacher - Missile Skirmish' },
    { ship_id: 629, fitting_name: 'Rupture - Armor Brawler' },
    { ship_id: 639, fitting_name: 'Tempest - Long Range' },
    { ship_id: 644, fitting_name: 'Typhoon - Mid-range Battleship' },
]

// ---------------------------------------------------------------------------------------------------------------
// A busy grid of Tech I fittings (sixteen cards, no meta-group corner icons)
// ---------------------------------------------------------------------------------------------------------------

const t1_hulls: [number, string, string][] = [
    [587, 'Rifter', 'Frigate'], [598, 'Breacher', 'Frigate'], [16242, 'Thrasher', 'Destroyer'],
    [622, 'Stabber', 'Cruiser'], [629, 'Rupture', 'Cruiser'], [24702, 'Hurricane', 'Battlecruiser'],
    [16231, 'Cyclone', 'Battlecruiser'], [639, 'Tempest', 'Battleship'], [644, 'Typhoon', 'Battleship'],
]
const t1_roles = [
    ['Brawler', ['nanogang', 'new_player_friendly']],
    ['Kite', ['faction_warfare']],
    ['Fleet', ['fleet_composition', 'nullsec']],
] as const

export const fittings_t1_busy: FittingItem[] = t1_hulls.flatMap(([ship_id, ship_name, ship_type], hull_index) =>
    t1_roles.slice(0, hull_index % 2 === 0 ? 2 : 1).map(([role, tags], role_index): FittingItem => ({
        id: 1300 + hull_index * 10 + role_index,
        fitting_name: `${ship_name} - ${role}`,
        fitting_type: role_index === 0 ? 'Primary' : 'Support',
        tags: [...tags],
        ship_type,
        ship_name,
        ship_id,
        ship_meta: 'Tech I',
        eft_format: `[${ship_name}, ${ship_name} - ${role}]\n\n5MN Microwarpdrive II\nWarp Scrambler II`,
    })),
).slice(0, 14).concat([
    { ...rifter_fitting, id: 1390, fitting_name: 'Rifter - Gate Camp' },
    { ...stabber_fitting, id: 1391, fitting_name: 'Stabber - Anti-Tackle' },
])

// ---------------------------------------------------------------------------------------------------------------
// Single modules and skills
// ---------------------------------------------------------------------------------------------------------------

export const fit_slot_single: CargoItem = { id: 2889, name: '200mm AutoCannon II' }
export const fit_slot_stacked: CargoItem = { id: 519, name: 'Gyrostabilizer II', amount: 3 }
export const fit_slot_officer_long: CargoItem = {
    id: 85010,
    name: "Ramaku's Modified 200mm AutoCannon (Officer, Faction Charges Loaded, Heat Damaged)",
}

export const skill_spt_v = { skill_name: 'Small Projectile Turret', skill_level: 5 }
export const skill_gunnery_iv = { skill_name: 'Gunnery', skill_level: 4 }
export const skill_logi_i = { skill_name: 'Logistics Cruisers', skill_level: 1 }

/** An unfilled slot: FittingCustom pushes null for it, and FittingSlot draws the slot-type placeholder instead of a module. */
export const fitting_slot_empty = null
