import type { BattleScope } from '@helpers/fleet_fights'
import type {
    FleetMember,
    Fleet,
    FleetDetail,
    FleetRequest,
    Audience,
    Location,
    FleetUsers,
    FleetStatus,
    FleetPatchRequest,
    FleetMetrics,
    FleetCommanderMetrics,
    FleetPingPreview,
    FleetPingPreviewRequest,
    RestrictedResponse,
    ApiResponse,
    ApiRequest,
} from '@dtypes/api.minmatar.org'
import { api_request, api_response, api_status_is } from '@helpers/api.minmatar.org/client'

const API_ENDPOINT = `${import.meta.env.API_URL}/api/fleets`

export async function get_locations(access_token:string) {
    return await api_request<Location[]>(`${API_ENDPOINT}/v2/locations`, {
        token: access_token,
        error: 'Error fetching fleet locations',
    })
}

export async function get_audiences(access_token:string) {
    return await api_request<Audience[]>(`${API_ENDPOINT}/audiences`, {
        token: access_token,
        error: 'Error fetching fleet audiences',
    })
}

/** `host_group_id` lists one tribe group's fleets (those the viewer can see). */
export async function get_fleets_v3(access_token:string, status:FleetStatus, host_group_id?:number | null) {
    const group = host_group_id ? `&host_group_id=${host_group_id}` : ''

    return await api_request<Fleet[]>(`${API_ENDPOINT}/v3?fleet_filter=${status}${group}`, {
        token: access_token,
        error: 'Error fetching fleets',
    })
}

/**
 * A fleet, or the group that hosts it when it is a members-only tribe
 * group fleet the viewer can't see (403 RestrictedResponse). Other errors,
 * including a plain 403, throw.
 */
export async function get_fleet_access(access_token:string, id:number):Promise<
    { fleet: FleetDetail, restricted: null } | { fleet: null, restricted: RestrictedResponse }
> {
    const response = await api_response(`${API_ENDPOINT}/${id}`, {
        token: access_token,
        error: 'Error fetching fleet',
        allow: [403],
    })
    const body = await response.json()

    if (response.status === 403) {
        if (body?.host_group)
            return { fleet: null, restricted: body as RestrictedResponse }

        throw new Error('Error fetching fleet: HTTP error! Status — 403', { cause: 403 })
    }

    return { fleet: body as FleetDetail, restricted: null }
}

/** The Discord start ping these fleet form fields would send (same builder as the real ping). */
export async function preview_fleet_ping(access_token:string, fleet:FleetPingPreviewRequest) {
    return await api_request<FleetPingPreview>(`${API_ENDPOINT}/ping-preview`, {
        method: 'POST',
        token: access_token,
        body: fleet,
        error: 'Error previewing fleet ping',
    })
}

/**
 * `fleet.campaign_id` is forwarded as-is: an id attaches the fleet to that
 * campaign, `null` schedules it unattached. The API answers 400 when the
 * campaign is not `scheduled`/`active` or does not exist.
 */
export async function create_fleet(access_token:string, fleet:FleetRequest) {
    return await api_request<Fleet>(API_ENDPOINT, {
        method: 'POST',
        token: access_token,
        body: fleet,
        error: 'Error creating fleet',
    })
}

/**
 * `fleet.campaign_id` is only sent when it is set on the payload: `null`
 * detaches the campaign, an id re-attaches it, and leaving it `undefined`
 * (JSON.stringify drops it) leaves the current campaign untouched.
 */
export async function update_fleet(access_token:string, fleet:FleetPatchRequest, fleet_id: number) {
    return await api_request<Fleet>(`${API_ENDPOINT}/${fleet_id}`, {
        method: 'PATCH',
        token: access_token,
        body: fleet,
        error: 'Error updating fleet',
    })
}

/** The new fleet, the fleet it was copied from, and the settings left off. */
export type FleetCopy = ApiResponse<'EveFleetCopyResponse'>

/**
 * Schedules a copy of the fleet at `start_time`. Throws with the backend's
 * reason unprefixed, so the dialog can show it to the FC as is.
 */
export async function copy_fleet(access_token:string, fleet_id:number, start_time:string) {
    return await api_request<FleetCopy>(`${API_ENDPOINT}/${fleet_id}/copy`, {
        method: 'POST',
        token: access_token,
        body: { start_time },
    })
}

export async function get_fleet_by_id(access_token:string, id:number) {
    return await api_request<FleetDetail>(`${API_ENDPOINT}/${id}`, {
        token: access_token,
        error: 'Error fetching fleet',
    })
}

export async function delete_fleet(access_token:string, id:number) {
    return await api_status_is(`${API_ENDPOINT}/${id}`, {
        method: 'DELETE',
        token: access_token,
        error: 'Error deleting fleet',
    })
}

export async function start_fleet_now(access_token: string, fc_character_id?: number): Promise<Fleet> {
    return await api_request<Fleet>(`${API_ENDPOINT}/start-now`, {
        method: 'POST',
        token: access_token,
        body: fc_character_id != null ? { fc_character_id } : undefined,
    })
}

export async function start_fleet(access_token:string, fleet_id:number) {
    return await api_status_is(`${API_ENDPOINT}/${fleet_id}/tracking`, {
        method: 'POST',
        token: access_token,
        error: 'Error starting the fleet',
    })
}

export async function get_fleet_members(access_token:string, id:number) {
    return await api_request<FleetMember[]>(`${API_ENDPOINT}/${id}/members`, {
        token: access_token,
        error: 'Error fetching fleet members',
    })
}

export async function get_fleet_users(access_token:string, fleet_id:number) {
    return await api_request<FleetUsers[]>(`${API_ENDPOINT}/${fleet_id}/users`, {
        token: access_token,
        error: 'Error fetching fleet',
    })
}

export interface FleetRoleVolunteer {
    id: number
    character_id: number
    character_name: string
    role: string
    subtype: string | null
    quantity: number | null
    solar_system_id?: number | null
    solar_system_name?: string | null
}

export async function get_fleet_role_volunteers(access_token: string, fleet_id: number): Promise<FleetRoleVolunteer[]> {
    return await api_request<FleetRoleVolunteer[]>(`${API_ENDPOINT}/${fleet_id}/role-volunteers`, {
        token: access_token,
    })
}

export async function create_fleet_role_volunteer(
    access_token: string,
    fleet_id: number,
    payload: { character_id: number; role: string; subtype?: string | null; quantity?: number | null }
): Promise<FleetRoleVolunteer> {
    return await api_request<FleetRoleVolunteer>(`${API_ENDPOINT}/${fleet_id}/role-volunteers`, {
        method: 'POST',
        token: access_token,
        body: payload,
    })
}

export async function delete_fleet_role_volunteer(access_token: string, fleet_id: number, volunteer_id: number): Promise<void> {
    await api_response(`${API_ENDPOINT}/${fleet_id}/role-volunteers/${volunteer_id}`, {
        method: 'DELETE',
        token: access_token,
    })
}

export async function refresh_fleet_motd(access_token: string, fleet_id: number): Promise<void> {
    await api_response(`${API_ENDPOINT}/${fleet_id}/refresh-motd`, {
        method: 'POST',
        token: access_token,
    })
}

export async function preping(access_token:string, fleet_id:number) {
    return await api_status_is(`${API_ENDPOINT}/${fleet_id}/preping`, {
        method: 'POST',
        token: access_token,
        error: 'Error creating pre-ping',
    })
}

/** Pass fleet_id for one fleet's row; the full list is a year of fleets. */
export async function get_fleets_metrics(access_token:string, fleet_id?:number) {
    const query = fleet_id ? `?fleet_id=${fleet_id}` : ''
    return await api_request<FleetMetrics[]>(`${API_ENDPOINT}/metrics${query}`, {
        token: access_token,
        error: 'Error fetching fleet metrics',
    })
}

export async function get_fleet_commander_metrics(access_token:string) {
    return await api_request<FleetCommanderMetrics[]>(`${API_ENDPOINT}/commander-metrics`, {
        token: access_token,
        error: 'Error fetching fleet commander metrics',
    })
}
// --- Cyno system assignment (on a pilot volunteered in a cyno fit) ----------

export async function assign_fleet_ship_volunteer_system(
    access_token: string,
    fleet_id: number,
    ship_volunteer_id: number,
    payload: { solar_system_id: number | null; solar_system_name: string | null }
): Promise<FleetShipVolunteer> {
    return await api_request<FleetShipVolunteer>(`${API_ENDPOINT}/${fleet_id}/ship-volunteers/${ship_volunteer_id}`, {
        method: 'PATCH',
        token: access_token,
        body: payload,
    })
}

// --- Fleet roles, worked out from ships --------------------------------------

export type BurstKind = 'armor' | 'shield' | 'skirmish' | 'information' | 'mining'

export interface FleetRolePilot {
    character_id: number
    character_name: string
    ship_id: number
    ship_name: string
    fitting_name: string
    source: 'volunteer' | 'in_fleet'
    in_fleet: boolean
    /** Bursts of the row's kind this pilot runs (links rows only). */
    count: number
    ship_volunteer_id: number | null
    solar_system_id?: number | null
    solar_system_name?: string | null
}

export interface FleetLinkCoverage {
    kind: BurstKind
    label: string
    pilots: FleetRolePilot[]
}

export interface FleetRoleCoverage {
    /** Logi FC is the one role still signed up for. */
    logi_fc: FleetRoleVolunteer[]
    links: FleetLinkCoverage[]
    cynos: FleetRolePilot[]
    logi: FleetRolePilot[]
}

export async function get_fleet_roles(access_token: string, fleet_id: number): Promise<FleetRoleCoverage> {
    return await api_request<FleetRoleCoverage>(`${API_ENDPOINT}/${fleet_id}/roles`, {
        token: access_token,
    })
}

// --- Ship volunteers (doctrine composition) ----------------------------------

export interface FleetShipVolunteer {
    id: number
    character_id: number
    character_name: string
    fitting_id: number | null
    fleet_fitting_id: number | null
    /** The fit's name; for an off-doctrine hull, the hull's name. */
    fitting_name: string
    ship_id: number
    /** Set when the pilot brings a hull outside the composition. */
    ship_type_id?: number | null
    off_doctrine?: boolean
    /** Command bursts this pilot runs online. */
    bursts: BurstKind[]
    solar_system_id?: number | null
    solar_system_name?: string | null
}

// --- Fleet composition (doctrine fits + fleet fittings) ---------------------

export type FleetCompositionSource = 'doctrine' | 'catalog' | 'manual'
export type FleetFittingRole = 'primary' | 'secondary' | 'support' | 'utility'

export interface FleetCompositionEntry {
    /** Stable key: `f:<fitting_id>` for catalog fits, `m:<fleet_fitting_id>` for manual fits. */
    key: string
    fitting_id: number | null
    fleet_fitting_id: number | null
    name: string
    ship_id: number
    ship_name: string
    /** EVE ship class (EveGroup name), e.g. "Dreadnought"; empty when unknown. */
    ship_group: string
    role: FleetFittingRole
    source: FleetCompositionSource
    eft_format: string
    refits: { id: number; name: string }[]
    /** Module name → slot for every module named in the EFT, when the universe cache knows it. */
    module_slots: Record<string, ModuleSlot>
    /** Links / cyno / logi this fit fills. */
    fit_roles: FleetFitRoles
}

export interface FleetFitRoles {
    links: boolean
    /** How many bursts the fit runs at once. */
    burst_slots: number
    bursts_online: Partial<Record<BurstKind, number>>
    bursts_fitted: Partial<Record<BurstKind, number>>
    cyno: boolean
    logi: boolean
}

export type ModuleSlot = 'high' | 'mid' | 'low' | 'rig'

/** Availability of one composition entry at the fleet's staging location. */
export interface FleetSupplyEntry {
    key: string
    fitting_id: number | null
    fleet_fitting_id: number | null
    /** Outstanding contracts for this fit at staging; null when contracts aren't tracked for it. */
    contracts: number | null
    /** Complete fits buyable from staging sell orders; null when the location has no market data. */
    market_fits: number | null
    /** Items with zero stock on the staging market (why market_fits is 0). */
    market_missing: string[]
}

export interface FleetSupply {
    entries: FleetSupplyEntry[]
}

export interface ShipSelection {
    character_id: number
    fitting_id?: number | null
    fleet_fitting_id?: number | null
    /** A hull outside the composition, instead of a fit. */
    ship_type_id?: number | null
    /** Bursts to run online; omitted = the fit's online bursts. */
    bursts?: BurstKind[] | null
}

/** The hull a character usually flies, as a composition entry; `fleets` = past fleets flown in it. */
export type ShipSuggestion = ApiResponse<'ShipSuggestionResponse'>

export interface MyFleetPilot {
    character_id: number
    character_name: string
    /** Joined a tracked fleet in the last 30 days. */
    recent_fleets: boolean
    selection: ShipSelection | null
    /** What they usually fly, until the caller first saves on this fleet. */
    suggestion?: ShipSuggestion | null
}

export async function get_fleet_my_pilots(access_token: string, fleet_id: number): Promise<MyFleetPilot[]> {
    return await api_request<MyFleetPilot[]>(`${API_ENDPOINT}/${fleet_id}/my-pilots`, {
        token: access_token,
    })
}

/** Replace the caller's ship volunteers: one ship per listed character, none = not flying. */
export async function set_my_ship_volunteers(access_token: string, fleet_id: number, selections: ShipSelection[]): Promise<FleetShipVolunteer[]> {
    return await api_request<FleetShipVolunteer[]>(`${API_ENDPOINT}/${fleet_id}/my-ship-volunteers`, {
        method: 'PUT',
        token: access_token,
        body: { selections },
    })
}

/** A custom EFT fit the caller has used on one of their fleets before. */
export interface MyFleetFitting {
    name: string
    ship_id: number
    ship_name: string
    eft_format: string
}

export async function get_my_fleet_fittings(access_token: string): Promise<MyFleetFitting[]> {
    return await api_request<MyFleetFitting[]>(`${API_ENDPOINT}/my-fittings`, {
        token: access_token,
    })
}

export async function get_fleet_supply(access_token: string, fleet_id: number): Promise<FleetSupply> {
    return await api_request<FleetSupply>(`${API_ENDPOINT}/${fleet_id}/supply`, {
        token: access_token,
    })
}

/** Payload target for volunteers/refits: catalog fit or manual fleet fit. */
export const composition_target = (entry: FleetCompositionEntry) =>
    entry.fitting_id ? { fitting_id: entry.fitting_id } : { fleet_fitting_id: entry.fleet_fitting_id as number }

export const volunteer_matches_entry = (volunteer: FleetShipVolunteer, entry: FleetCompositionEntry) =>
    entry.fitting_id ? volunteer.fitting_id === entry.fitting_id : volunteer.fleet_fitting_id === entry.fleet_fitting_id

export async function get_fleet_composition(access_token: string, fleet_id: number): Promise<FleetCompositionEntry[]> {
    return await api_request<FleetCompositionEntry[]>(`${API_ENDPOINT}/${fleet_id}/composition`, {
        token: access_token,
    })
}

export async function create_fleet_fitting(
    access_token: string,
    fleet_id: number,
    payload: { fitting_id?: number | null; eft_format?: string | null; role?: FleetFittingRole }
): Promise<FleetCompositionEntry> {
    return await api_request<FleetCompositionEntry>(`${API_ENDPOINT}/${fleet_id}/fittings`, {
        method: 'POST',
        token: access_token,
        body: payload,
    })
}

export async function delete_fleet_fitting(access_token: string, fleet_id: number, fleet_fitting_id: number): Promise<void> {
    await api_response(`${API_ENDPOINT}/${fleet_id}/fittings/${fleet_fitting_id}`, {
        method: 'DELETE',
        token: access_token,
    })
}

export async function get_fleet_ship_volunteers(access_token: string, fleet_id: number): Promise<FleetShipVolunteer[]> {
    return await api_request<FleetShipVolunteer[]>(`${API_ENDPOINT}/${fleet_id}/ship-volunteers`, {
        token: access_token,
    })
}


export async function delete_fleet_ship_volunteer(access_token: string, fleet_id: number, volunteer_id: number): Promise<void> {
    await api_response(`${API_ENDPOINT}/${fleet_id}/ship-volunteers/${volunteer_id}`, {
        method: 'DELETE',
        token: access_token,
    })
}

// --- Fleet refits (cargo to carry per doctrine fit) --------------------------

export interface FleetRefitModule {
    name: string
    quantity: number
    type_id: number | null
}

export interface FleetRefit {
    id: number
    fitting_id: number | null
    fleet_fitting_id: number | null
    fitting_name: string
    ship_id: number
    refit_id: number | null
    name: string
    cargo_modules: string
    modules: FleetRefitModule[]
    notes: string
    /** Full EFT of the refitted ship; empty for plain cargo lists. */
    eft_format: string
    /** In-game saved fitting created under the FC, until the fleet closes. */
    esi_fitting_id: number | null
}

/** One slot swap: fitted module out, cargo module in. */
export interface FleetRefitSwap {
    module_out: string
    module_in: string
}

export interface FleetRefitRequest {
    fitting_id?: number | null
    fleet_fitting_id?: number | null
    refit_id?: number | null
    name?: string | null
    cargo_modules?: string | null
    notes?: string | null
    /** Custom refit from slot swaps; the backend derives cargo/notes and saves the fit in-game. */
    swaps?: FleetRefitSwap[] | null
}

/** Whether the FC can save refits / custom fits in-game (needs an ESI scope). */
export interface FleetFittingAccess {
    can_publish: boolean
    scope: string
    token_type: string
    character_id: number | null
    character_name: string | null
}

export async function get_fleet_fitting_access(access_token: string, fleet_id: number): Promise<FleetFittingAccess> {
    return await api_request<FleetFittingAccess>(`${API_ENDPOINT}/${fleet_id}/fitting-access`, {
        token: access_token,
    })
}

export async function get_fleet_refits(access_token: string, fleet_id: number): Promise<FleetRefit[]> {
    return await api_request<FleetRefit[]>(`${API_ENDPOINT}/${fleet_id}/refits`, {
        token: access_token,
    })
}

export async function create_fleet_refit(access_token: string, fleet_id: number, payload: FleetRefitRequest): Promise<FleetRefit> {
    return await api_request<FleetRefit>(`${API_ENDPOINT}/${fleet_id}/refits`, {
        method: 'POST',
        token: access_token,
        body: payload,
    })
}

export async function delete_fleet_refit(access_token: string, fleet_id: number, refit_id: number): Promise<void> {
    await api_response(`${API_ENDPOINT}/${fleet_id}/refits/${refit_id}`, {
        method: 'DELETE',
        token: access_token,
    })
}

export interface FleetKillmail {
    killmail_id:            number;
    killmail_time:          string;
    outcome:                'kill' | 'loss';
    solar_system_id:        number;
    solar_system_name:      string;
    victim_ship_type_id:    number | null;
    victim_ship_name:       string;
    victim_character_id:    number | null;
    victim_character_name:  string;
    isk_value:              number;
    fleet_pilots:           number;
    is_capsule:             boolean;
}

export interface FleetKills {
    fleet_id:           number;
    tracked:            boolean;
    isk_destroyed:      number;
    isk_lost:           number;
    ships_destroyed:    number;
    pods_destroyed:     number;
    ships_lost:         number;
    pods_lost:          number;
    killmails:          FleetKillmail[];
}

export async function get_fleet_kills(access_token: string, fleet_id: number): Promise<FleetKills> {
    return await api_request<FleetKills>(`${API_ENDPOINT}/${fleet_id}/kills`, {
        token: access_token,
    })
}

export interface FleetResult {
    fleet_id:           number;
    isk_destroyed:      number;
    isk_lost:           number;
    ships_destroyed:    number;
    pods_destroyed:     number;
    ships_lost:         number;
    pods_lost:          number;
}

// Stored kill totals for finished fleets. Fleets without a stored card are left out.
export async function get_fleet_results(access_token: string, fleet_ids: number[]): Promise<FleetResult[]> {
    if (fleet_ids.length === 0)
        return []

    return await api_request<FleetResult[]>(`${API_ENDPOINT}/results?fleet_ids=${fleet_ids.join(',')}`, {
        token: access_token,
    })
}

export interface FleetSrpLoss {
    killmail_id:        number;
    killmail_time:      string;
    character_id:       number;
    character_name:     string;
    ship_type_id:       number;
    ship_name:          string;
    amount:             number;
    filed:              boolean;
}

// The caller's ship losses in a fleet on hulls SRP covers.
export async function get_fleet_my_srp(access_token: string, fleet_id: number): Promise<FleetSrpLoss[]> {
    return await api_request<FleetSrpLoss[]>(`${API_ENDPOINT}/${fleet_id}/my-srp`, {
        token: access_token,
    })
}

export interface MissingSignups {
    pilots: { character_id: number; character_name: string; ship_name: string; cyno: boolean }[];
    last_nudge: { sent_at: string; players: number; delivered: number; failed: number } | null;
    next_nudge_at: string | null;
}

// FC and managers: signed-up pilots not in the live fleet, and the last DM nudge.
export async function get_fleet_missing_signups(access_token: string, fleet_id: number): Promise<MissingSignups> {
    return await api_request<MissingSignups>(`${API_ENDPOINT}/${fleet_id}/missing-signups`, {
        token: access_token,
    })
}

// Queue one DM per player who signed up but is not in fleet. 429 while cooling down.
export async function nudge_fleet_missing_signups(access_token: string, fleet_id: number): Promise<{ pilots: number }> {
    return await api_request<{ pilots: number }>(`${API_ENDPOINT}/${fleet_id}/missing-signups/nudge`, {
        method: 'POST',
        token: access_token,
    })
}

export type FleetFights = ApiResponse<'EveFleetFightsResponse'>
export type FleetFightRound = ApiResponse<'FleetFightRound'>
export type FleetFightKillmail = ApiResponse<'FleetFightKillmail'>
export type FleetFightEvent = ApiResponse<'FleetFightEvent'>

/**
 * The fleet's killmails cut into rounds. Null when the viewer may not see
 * them (403: while live, only the FC, fleet managers and pilots in fleet).
 */
export async function get_fleet_fights(access_token: string, fleet_id: number): Promise<FleetFights | null> {
    return await api_request<FleetFights | null>(`${API_ENDPOINT}/${fleet_id}/fights`, {
        token: access_token,
        allow: [403, 404],
    })
}

// Fleet managers fix where rounds start and end; each returns the re-cut timeline.
export async function merge_fleet_fights(access_token: string, fleet_id: number, start: string, end: string): Promise<FleetFights> {
    return await api_request<FleetFights>(`${API_ENDPOINT}/${fleet_id}/fights/merge`, {
        method: 'POST',
        token: access_token,
        body: { start, end },
    })
}

export async function split_fleet_fights(access_token: string, fleet_id: number, at: string): Promise<FleetFights> {
    return await api_request<FleetFights>(`${API_ENDPOINT}/${fleet_id}/fights/split`, {
        method: 'POST',
        token: access_token,
        body: { at },
    })
}

export async function undo_fleet_fights_edit(access_token: string, fleet_id: number, edit_id: number): Promise<FleetFights> {
    return await api_request<FleetFights>(`${API_ENDPOINT}/${fleet_id}/fights/edits/${edit_id}`, {
        method: 'DELETE',
        token: access_token,
    })
}

export async function reset_fleet_fights(access_token: string, fleet_id: number): Promise<FleetFights> {
    return await api_request<FleetFights>(`${API_ENDPOINT}/${fleet_id}/fights/edits`, {
        method: 'DELETE',
        token: access_token,
    })
}

// --- Overview: where the viewer's characters are ---------------------------

/** One of the viewer's characters; no location when its token lacks esi-location.read_location.v1. */
export type FleetPilotLocation = ApiResponse<'MyPilotLocationResponse'>

export async function get_fleet_my_pilot_locations(access_token: string, fleet_id: number): Promise<FleetPilotLocation[]> {
    return await api_request<FleetPilotLocation[]>(`${API_ENDPOINT}/${fleet_id}/my-pilot-locations`, {
        token: access_token,
    })
}

// --- Participants after the fleet ------------------------------------------

/**
 * Who flew a fleet: each pilot once by the first ship they undocked in, the
 * roles flown, and (for the fleet's managers only, else null) the no-shows.
 */
export type FleetParticipants = ApiResponse<'FleetParticipantsResponse'>

export type FleetBattleReport = ApiResponse<'FleetBattleReportResponse'>
export type FleetBattleSegment = ApiResponse<'FleetBattleSegment'>

/** The fleet's battle report, or a window of it; null when the viewer may not see it. */
export async function get_fleet_battle_report(access_token: string, fleet_id: number, scope: BattleScope = {}): Promise<FleetBattleReport | null> {
    const params = new URLSearchParams()
    if (scope.segment) params.set('segment', scope.segment.toString())
    else if (scope.start && scope.end) {
        params.set('start', scope.start)
        params.set('end', scope.end)
    }
    if (scope.sides) params.set('sides', scope.sides)
    const query = params.size ? `?${params}` : ''
    return await api_request<FleetBattleReport | null>(`${API_ENDPOINT}/${fleet_id}/fights/report${query}`, {
        token: access_token,
        allow: [403, 404],
    })
}

// The fleet's FC saves and removes battle report windows for everyone.
export async function create_fleet_battle_segment(access_token: string, fleet_id: number, name: string, start: string, end: string): Promise<FleetBattleSegment> {
    return await api_request<FleetBattleSegment>(`${API_ENDPOINT}/${fleet_id}/fights/segments`, {
        method: 'POST',
        token: access_token,
        body: { name, start, end },
    })
}

export async function delete_fleet_battle_segment(access_token: string, fleet_id: number, segment_id: number): Promise<void> {
    await api_request<null>(`${API_ENDPOINT}/${fleet_id}/fights/segments/${segment_id}`, {
        method: 'DELETE',
        token: access_token,
    })
}

export type FleetPublicKills = ApiResponse<'FleetPublicKillsResponse'>

/** A finished fleet's killmails for anyone, signed in or not; null when it isn't public. */
export async function get_fleet_public_kills(fleet_id: number): Promise<FleetPublicKills | null> {
    return await api_request<FleetPublicKills | null>(`${API_ENDPOINT}/${fleet_id}/public-kills`, {
        allow: [404],
    })
}

/** Who flew; with ``engagement`` (a 1-based rounds position) only that engagement. */
export async function get_fleet_participants(access_token: string, fleet_id: number, engagement?: number): Promise<FleetParticipants> {
    const query = engagement ? `?engagement=${engagement}` : ''
    return await api_request<FleetParticipants>(`${API_ENDPOINT}/${fleet_id}/participants${query}`, {
        token: access_token,
    })
}

// Private fleets and ship targets (docs/fleets/private-fleets.md).

export type FleetInvites = ApiResponse<'FleetInvitesResponse'>
export type FleetInvitePilot = ApiResponse<'InvitePilot'>
export type FleetInviteWave = ApiResponse<'InviteWave'>
export type FleetWavePreview = ApiResponse<'WavePreviewResponse'>
export type FleetWaveRequest = ApiRequest<'WaveRequest'>
export type FleetInviteCandidate = ApiResponse<'InviteCandidate'>
export type ShipTargetProgress = ApiResponse<'ShipTargetProgress'>
export type ShipTargetLine = ApiRequest<'ShipTargetLine'>

/** The FC's and Strategic FCs' view of a private fleet's invites. */
export async function get_fleet_invites(access_token:string, fleet_id:number) {
    return await api_request<FleetInvites>(`${API_ENDPOINT}/${fleet_id}/invites`, {
        token: access_token,
        error: 'Error fetching fleet invites',
    })
}

/** Who a wave with these picks would reach. */
export async function preview_fleet_wave(access_token:string, fleet_id:number, wave:FleetWaveRequest) {
    return await api_request<FleetWavePreview>(`${API_ENDPOINT}/${fleet_id}/invites/preview`, {
        method: 'POST',
        token: access_token,
        body: wave,
    })
}

/** Invite the new players in these picks. Throws with the backend's reason. */
export async function send_fleet_wave(access_token:string, fleet_id:number, wave:FleetWaveRequest) {
    return await api_request<{ number: number, invited: number, will_dm: number }>(`${API_ENDPOINT}/${fleet_id}/invites/waves`, {
        method: 'POST',
        token: access_token,
        body: wave,
    })
}

/** DM everyone who hasn't answered once more; 429 while cooling down. */
export async function reping_fleet_invites(access_token:string, fleet_id:number) {
    return await api_request<{ pilots: number }>(`${API_ENDPOINT}/${fleet_id}/invites/reping`, {
        method: 'POST',
        token: access_token,
    })
}

export async function get_fleet_invite_candidates(access_token:string, fleet_id:number, q:string) {
    return await api_request<FleetInviteCandidate[]>(`${API_ENDPOINT}/${fleet_id}/invites/candidates?q=${encodeURIComponent(q)}`, {
        token: access_token,
    }) ?? []
}

/** Sit out a private fleet you were invited to. */
export async function sit_out_fleet(access_token:string, fleet_id:number) {
    return await api_request<{ invite_id: number, answer: string }>(`${API_ENDPOINT}/${fleet_id}/invites/me/out`, {
        method: 'POST',
        token: access_token,
    })
}

export async function declassify_fleet(access_token:string, fleet_id:number) {
    return await api_request<{ fleet_id: number, declassified_at: string }>(`${API_ENDPOINT}/${fleet_id}/declassify`, {
        method: 'POST',
        token: access_token,
    })
}

export async function get_fleet_targets(access_token:string, fleet_id:number) {
    return await api_request<ShipTargetProgress[]>(`${API_ENDPOINT}/${fleet_id}/targets`, {
        token: access_token,
    }) ?? []
}

/** Replace the fleet's ship targets. Throws with the backend's reason. */
export async function put_fleet_targets(access_token:string, fleet_id:number, lines:ShipTargetLine[]) {
    return await api_request<ShipTargetProgress[]>(`${API_ENDPOINT}/${fleet_id}/targets`, {
        method: 'PUT',
        token: access_token,
        body: { lines },
    })
}
