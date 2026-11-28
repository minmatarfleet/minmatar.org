// Fixtures for the Corporations and tribes feature stories. Names of pilots other than the
// EVE.character_* one are invented; corporation and alliance ids are real.
import type {
    ApplicationBasic,
    CorporationBasic,
    CorporationObject,
    TribeEventRowUI,
    TribeGroupRefUI,
} from '@dtypes/layout_components'
import type { CorporationLeadershipMember, DepartureGroup, ExitSurveyForm, FlaggedJoin, HistoryEntry, TrialProgress, TribeMembership } from '@dtypes/api.minmatar.org'
import { EVE } from '../../stories/_controls'

// Corporations -----------------------------------------------------------------------------

export const a_rat: CorporationObject = {
    corporation_id: EVE.corporation_id,
    corporation_name: EVE.corporation_name,
    alliance_id: EVE.alliance_id,
    alliance_name: EVE.alliance_name,
    active: true,
    trial: false,
    corporation_type: 'alliance',
    status: 'available',
}

/** a_rat for a pilot who fails two required recruitment checks. */
export const a_rat_blocked: CorporationObject = {
    ...a_rat,
    requirements_blocked: true,
    requirements_unmet: ['Fly our Cruisers doctrine', 'A character with 20M+ skill points'],
}

const other_corps: CorporationObject[] = [
    { corporation_id: 98685730, corporation_name: 'Minmatar Fleet Academy', alliance_id: EVE.alliance_id, alliance_name: EVE.alliance_name, active: true, trial: true, corporation_type: 'alliance', status: 'available' },
    { corporation_id: 98644291, corporation_name: 'Tribal Liberation Force', alliance_id: EVE.alliance_id, alliance_name: EVE.alliance_name, active: true, trial: false, corporation_type: 'alliance', status: 'pending' },
    { corporation_id: 98720311, corporation_name: 'Sebiestor Industrial Combine', alliance_id: EVE.alliance_id, alliance_name: EVE.alliance_name, active: true, trial: false, corporation_type: 'alliance', status: 'available' },
    { corporation_id: 98701177, corporation_name: 'Krusual Trade Syndicate', alliance_id: EVE.alliance_id, alliance_name: EVE.alliance_name, active: true, trial: false, corporation_type: 'associate', status: 'available' },
    { corporation_id: 98733455, corporation_name: 'Thukker Wayfarers', alliance_id: EVE.alliance_id, alliance_name: EVE.alliance_name, active: true, trial: false, corporation_type: 'alliance', status: 'rejected' },
    { corporation_id: 98750812, corporation_name: 'Brutor Vanguard', alliance_id: EVE.alliance_id, alliance_name: EVE.alliance_name, active: true, trial: false, corporation_type: 'militia', status: 'available' },
]

export const corporations_typical: CorporationObject[] = [a_rat, ...other_corps]

export const corporations_busy: CorporationObject[] = [
    ...corporations_typical,
    ...Array.from({ length: 12 }, (_, i): CorporationObject => ({
        corporation_id: 98800000 + i,
        corporation_name: `Ember Wing ${['Alpha', 'Bravo', 'Charlie', 'Delta', 'Echo', 'Foxtrot', 'Golf', 'Hotel', 'India', 'Juliet', 'Kilo', 'Lima'][i]}`,
        alliance_id: EVE.alliance_id,
        alliance_name: EVE.alliance_name,
        active: true,
        trial: i % 5 === 0,
        corporation_type: 'alliance',
        status: 'available',
    })),
]

export const corporation_no_alliance: CorporationObject = {
    corporation_id: 98812345,
    corporation_name: 'The Quiet Moon Hauling and Reprocessing Cooperative of the Great Minmatar Republic',
    alliance_id: null,
    alliance_name: null,
    active: true,
    corporation_type: 'public',
    status: 'available',
}

export const corporation_trial: CorporationObject = { ...other_corps[0] }

// Applications -----------------------------------------------------------------------------

export const application_corporation: CorporationBasic = { id: EVE.corporation_id, name: EVE.corporation_name }

export const application_pending: ApplicationBasic = {
    id: 4412,
    applied_corporation: EVE.corporation_id,
    character_id: EVE.character_id,
    character_name: EVE.character_name,
    corporation_id: 98685730,
    corporation_name: 'Minmatar Fleet Academy',
    status: 'pending',
}

export const application_second: ApplicationBasic = {
    id: 4413,
    applied_corporation: EVE.corporation_id,
    character_id: 2119001147,
    character_name: 'Vaska Tennen',
    corporation_id: 1000115,
    corporation_name: 'University of Caille',
    status: 'pending',
}

// A character with no id (id 0) is an application whose pilot is gone: only Deny is offered.
export const application_orphan: ApplicationBasic = {
    id: 4414,
    applied_corporation: EVE.corporation_id,
    character_id: 0,
    character_name: 'Unknown pilot',
    corporation_id: 1000115,
    corporation_name: 'University of Caille',
    status: 'pending',
}

// Tribe groups and events ------------------------------------------------------------------

export const group_capitals: TribeGroupRefUI = { id: 3, code: 'capitals', name: 'Capitals', tribe_id: 1, tribe_name: 'Warfare' }
export const group_mining: TribeGroupRefUI = { id: 7, code: 'mining', name: 'Mining', tribe_id: 2, tribe_name: 'Supply' }
export const group_long: TribeGroupRefUI = {
    id: 11,
    code: 'long',
    name: 'Faction Warfare Frigate Skirmishers of Amamake',
    tribe_id: 1,
    tribe_name: 'Warfare',
}

const ISO = (day: number, hour: number, minute = 0) => new Date(Date.UTC(2026, 10, day, hour, minute)).toISOString()

export const event_scheduled: TribeEventRowUI = {
    id: 501,
    title: 'Capital Doctrine Night: Nidhoggur logistics',
    cover_url: null,
    starts_at: ISO(24, 19),
    ends_at: ISO(24, 21),
    where_kind: 'stage',
    where_label: 'Capitals Stage',
    recurrence_label: 'Weekly',
    status: 'scheduled',
    interested_count: 23,
    discord_event_url: 'https://discord.com/events/1000/501',
    edit_href: null,
}

export const event_editable: TribeEventRowUI = {
    ...event_scheduled,
    id: 502,
    title: 'Rattini Tribe fleet doctrine review',
    recurrence_label: null,
    where_kind: 'voice',
    where_label: 'Fleet Voice 2',
    interested_count: 8,
    edit_href: '/alliance/tribes/1/3/events/502/edit/',
}

export const event_cancelled: TribeEventRowUI = {
    ...event_scheduled,
    id: 503,
    title: 'Titan assembly at Auga',
    recurrence_label: null,
    status: 'cancelled',
    interested_count: 41,
}

export const event_completed: TribeEventRowUI = {
    ...event_scheduled,
    id: 504,
    title: 'Hauler escort run to Rens',
    starts_at: ISO(15, 18),
    ends_at: ISO(15, 20),
    recurrence_label: null,
    where_kind: 'place',
    where_label: 'Amamake gate',
    status: 'completed',
    interested_count: 17,
}

export const event_no_date: TribeEventRowUI = {
    id: 505,
    title: 'Moon mining kickoff',
    cover_url: null,
    starts_at: null,
    ends_at: null,
    where_kind: 'voice',
    where_label: 'Mining Voice',
    recurrence_label: null,
    status: 'scheduled',
    interested_count: 0,
    discord_event_url: null,
    edit_href: null,
}

export const event_no_end: TribeEventRowUI = { ...event_scheduled, id: 506, ends_at: null, recurrence_label: null }

export const events_week: TribeEventRowUI[] = [event_scheduled, event_editable, event_no_end, event_no_date, event_completed, event_cancelled]

// Trial progress ---------------------------------------------------------------------------

export const trial_on_pace: TrialProgress = { day: 18, on_pace: true, review_day: 28, scale_days: 45, average_days: 34, average_scope: 'corporation' }
export const trial_behind: TrialProgress = { day: 31, on_pace: false, review_day: 28, scale_days: 45, average_days: 34, average_scope: 'corporation' }
export const trial_alliance_average: TrialProgress = { ...trial_on_pace, day: 9, average_days: 38, average_scope: 'alliance' }
export const trial_no_average: TrialProgress = { day: 5, on_pace: true, review_day: 28, scale_days: 45, average_days: null, average_scope: null }
export const trial_overdue: TrialProgress = { day: 62, on_pace: false, review_day: 28, scale_days: 45, average_days: 34, average_scope: 'corporation' }

const tz = (...brackets: string[]) => ({ brackets, secondary: [], source: 'declared', weekend: [] })

// Leadership -------------------------------------------------------------------------------

export const leadership_full: CorporationLeadershipMember[] = [
    { character_id: EVE.character_id, character_name: EVE.character_name, role: 'ceo', on_leave: false, timezone: tz('USTZ') },
    { character_id: 2119001147, character_name: 'Vaska Tennen', role: 'director', on_leave: false, timezone: tz('EUTZ') },
    { character_id: 2119002203, character_name: 'Ordan Sebiestor', role: 'director', on_leave: false, timezone: tz('AUTZ') },
    { character_id: 2119003310, character_name: 'Hela Brutori', role: 'director', on_leave: true, timezone: tz('USTZ', 'EUTZ') },
    { character_id: 2119004419, character_name: 'Tavi Krusual', role: 'director', on_leave: false, timezone: tz() },
]
export const leadership_ceo_only: CorporationLeadershipMember[] = [leadership_full[0]]
export const leadership_directors_only: CorporationLeadershipMember[] = leadership_full.slice(1, 3)

// Tribe memberships ------------------------------------------------------------------------

const membership_base: TribeMembership = {
    id: 9021,
    user_id: 311,
    tribe_group_id: 3,
    tribe_group_name: 'Capitals',
    tribe_id: 1,
    status: 'active',
    rank_id: 2,
    rank_code: 'pilot',
    rank_name: 'Capital Pilot',
    inactive_reason: null,
    requirement_snapshot: null,
    created_at: '2026-08-02T10:00:00Z',
    approved_by_id: 12,
    approved_at: '2026-08-04T12:30:00Z',
    left_at: null,
    primary_character_id: EVE.character_id,
    primary_character_name: EVE.character_name,
    characters: [
        { id: 1, character_id: EVE.character_id, character_name: EVE.character_name, committed_at: '2026-08-04T12:30:00Z', left_at: null, qualifies: true, missing_skills: false, missing_assets: false, missing_token: false },
        { id: 2, character_id: 2119001147, character_name: 'Vaska Tennen', committed_at: '2026-08-05T09:00:00Z', left_at: null, qualifies: false, missing_skills: true, missing_assets: false, missing_token: false },
        { id: 3, character_id: 2119002203, character_name: 'Ordan Sebiestor', committed_at: '2026-08-06T09:00:00Z', left_at: null, qualifies: false, missing_skills: false, missing_assets: true, missing_token: false },
        { id: 4, character_id: 2119003310, character_name: 'Hela Brutori', committed_at: '2026-08-07T09:00:00Z', left_at: null, qualifies: null, missing_skills: null, missing_assets: null, missing_token: true },
    ],
}

export const membership_with_alts: TribeMembership = membership_base
export const membership_no_alts: TribeMembership = { ...membership_base, id: 9022, characters: [] }
export const membership_no_rank: TribeMembership = {
    ...membership_base,
    id: 9023,
    rank_id: null,
    rank_code: null,
    rank_name: null,
    primary_character_id: null,
    primary_character_name: 'Ashen Rattini-Sebiestor of the Seventh Convoy',
    characters: [],
}


// Departures tab (#3198): invented pilots; 1000167 is Pator Tech School, a real NPC corporation.
const departure = (fields: Partial<DepartureGroup>): DepartureGroup => ({
    departure_ids: [101],
    character_id: 2112000101,
    character_name: 'Arkan Veld',
    alt_names: [],
    registered: true,
    months_in_corporation: 14,
    first_missing_at: '2026-11-20T12:00:00Z',
    destination_corporation_id: 1000167,
    destination_name: 'Pator Tech School',
    kind: 'exit',
    destination_is_npc: true,
    reason: '',
    can_rejoin: null,
    note: '',
    flag_id: null,
    survey_sent_at: null,
    ...fields,
})

export const departures_open: DepartureGroup[] = [
    departure({}),
    departure({ departure_ids: [102], character_id: 2112000102, character_name: 'Mira Stonehand', registered: false, months_in_corporation: null, destination_name: 'Republic University', destination_corporation_id: 1000168 }),
    departure({ departure_ids: [103], character_id: 2112000103, character_name: 'Kesh Varo', months_in_corporation: 3, kind: 'alliance_move', destination_is_npc: false, destination_corporation_id: 98000002, destination_name: 'Tribal Liberation Force', reason: 'left' }),
    departure({ departure_ids: [104], character_id: 2112000104, character_name: 'Dren Halvik', months_in_corporation: 1, reason: 'kicked_other', can_rejoin: false, note: 'Awoxed a corp Orca', flag_id: 7 }),
]

export const departures_answered: DepartureGroup[] = [
    departure({ reason: 'kicked_inactive', can_rejoin: true }),
    departure({ departure_ids: [105], character_id: 2112000105, character_name: 'Lyss Corran', reason: 'left', survey_sent_at: '2026-11-06T12:00:00Z' }),
]

export const departures_with_alts: DepartureGroup[] = [
    departure({ departure_ids: [106, 107, 108], character_id: 2112000106, character_name: 'Toren Ashblade', alt_names: ['Toren Alt', 'Toren Hauler'], kind: 'exit', destination_is_npc: false, destination_corporation_id: 98000003, destination_name: 'Brave Newbies Inc.' }),
]

// Alliance history on the application page (#3198): invented corporations and pilots.
export const history_flagged: HistoryEntry[] = [
    { departure_id: 1, corporation_id: 98000001, corporation_name: 'Example Corp', left_at: '2026-11-09T12:00:00Z', reason: 'kicked_other', can_rejoin: false, note: 'Awoxed a corp Orca', answered_by_name: 'Arkan Veld', flag_active: true },
    { departure_id: 2, corporation_id: 98000002, corporation_name: 'Second Corp', left_at: '2026-09-02T12:00:00Z', reason: 'kicked_inactive', can_rejoin: true, note: 'Gone 3 months, no word', answered_by_name: 'Sela Morn', flag_active: false },
    { departure_id: 3, corporation_id: 98000003, corporation_name: 'Third Corp', left_at: '2026-05-14T12:00:00Z', reason: 'left', can_rejoin: null, note: '', answered_by_name: 'Toma Vey', flag_active: false },
]

export const history_inactive_only: HistoryEntry[] = [history_flagged[1]]

export const flagged_joins: FlaggedJoin[] = [
    { id: 1, character_id: 2112000104, character_name: 'Dren Halvik', seen_at: '2026-11-22T12:00:00Z', removal_expected: false, flags: [history_flagged[0]] },
    { id: 2, character_id: 2112000109, character_name: 'Vex Arlen', seen_at: '2026-11-21T12:00:00Z', removal_expected: true, flags: [history_flagged[0]] },
]

// Exit survey page (#3198): the questions of definition version 1.
const survey_question = (key: string, type: string, label: string, fields: Record<string, unknown> = {}) => ({
    key, type, label, help: '', choices: [] as string[], rows: [], required: false, trendable: false,
    group: '', scale_labels: null as string[] | null, scale_kind: '', context: null, ...fields,
})
const survey_ratings = (corporation: string) => ({
    key: 'exit.ratings', title: 'Your time in the corporation', description: '',
    questions: [
        survey_question('exit.enjoyment', 'scale5', `Overall, how much did you enjoy ${corporation}?`, { required: true, scale_labels: ['Not at all', 'A lot'] }),
        survey_question('exit.leadership', 'scale5', 'Leadership', { required: true, scale_labels: ['Poor', 'Great'] }),
        survey_question('exit.activity', 'scale5', 'Activity and content', { required: true, scale_labels: ['Poor', 'Great'] }),
        survey_question('exit.welcome', 'scale5', 'Feeling welcome and included', { required: true, scale_labels: ['Poor', 'Great'] }),
    ],
})

export const exit_survey_form = {
    definition_key: 'exit', title: 'Exit survey', corporation_id: 98000001, corporation_name: 'Example Corp',
    character_name: 'Kesh Varo', member_from: '2026-08-02T12:00:00Z', member_to: '2026-11-15T12:00:00Z',
    kind: 'exit', new_corporation_name: null,
    blocks: [
        survey_ratings('Example Corp'),
        { key: 'exit.leaving', title: 'Leaving', description: '', questions: [
            survey_question('exit.why_left', 'multi', 'Why did you leave?', { help: 'Pick any that fit', choices: ['I was inactive in EVE', 'The corporation was inactive', 'Leadership issues', 'Timezone', 'I wanted different content', 'I joined friends elsewhere', "I'm quitting EVE", 'Other'] }),
            survey_question('exit.problem', 'text', 'Was there a problem with the corporation we should know about?'),
            survey_question('exit.anything_else', 'text', 'Anything else?'),
        ] },
    ],
} as unknown as ExitSurveyForm

export const alliance_move_survey_form = {
    ...exit_survey_form, definition_key: 'alliance_move', title: 'Alliance move survey', kind: 'alliance_move',
    new_corporation_name: 'Tribal Liberation Force', member_from: null,
    blocks: [
        survey_ratings('Example Corp'),
        { key: 'move.moving', title: 'Moving', description: '', questions: [
            survey_question('move.why', 'text', 'Why did you move to Tribal Liberation Force?'),
            survey_question('move.onboarding', 'scale5', "What was Tribal Liberation Force's onboarding like?", { scale_labels: ['Poor', 'Great'] }),
        ] },
    ],
} as unknown as ExitSurveyForm
