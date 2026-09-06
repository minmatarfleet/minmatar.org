import type {
    FleetMember,
    Fleet,
    FleetRequest,
    Audience,
    Location,
    FleetUsers,
    FleetStatus,
    FleetPatchRequest,
    FleetMetrics,
    FleetCommanderMetrics,
} from '@dtypes/api.minmatar.org'
import { get_error_message, parse_error_message, parse_response_error } from '@helpers/string'

const API_ENDPOINT = `${import.meta.env.API_URL}/api/fleets`

export async function get_types(access_token:string) {
    const headers = {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${access_token}`
    }

    const ENDPOINT = `${API_ENDPOINT}/types`

    console.log(`Requesting: ${ENDPOINT}`)

    try {
        const response = await fetch(ENDPOINT, {
            headers: headers
        })

        // console.log(response)

        if (!response.ok) {
            throw new Error(get_error_message(
                response.status,
                `GET ${ENDPOINT}`
            ), {
                cause: response.status
            });
        }

        return await response.json() as string[];
    } catch (error) {
        throw new Error(`Error fetching fleet types: ${error.message}`, { cause: error.cause });
    }
}

export async function get_locations(access_token:string) {
    const headers = {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${access_token}`
    }

    const ENDPOINT = `${API_ENDPOINT}/v2/locations`

    console.log(`Requesting: ${ENDPOINT}`)

    try {
        const response = await fetch(ENDPOINT, {
            headers: headers
        })

        // console.log(response)

        if (!response.ok) {
            throw new Error(await parse_response_error(response, `GET ${ENDPOINT}`), {
                cause: response.status
            });
        }

        return await response.json() as Location[];
    } catch (error) {
        throw new Error(`Error fetching fleet locations: ${error.message}`, { cause: error.cause });
    }
}

export async function get_audiences(access_token:string) {
    const headers = {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${access_token}`
    }

    const ENDPOINT = `${API_ENDPOINT}/audiences`

    console.log(`Requesting: ${ENDPOINT}`)

    try {
        const response = await fetch(ENDPOINT, {
            headers: headers
        })

        // console.log(response)

        if (!response.ok) {
            throw new Error(await parse_response_error(response, `GET ${ENDPOINT}`), {
                cause: response.status
            });
        }

        return await response.json() as Audience[];
    } catch (error) {
        throw new Error(`Error fetching fleet audiences: ${error.message}`, { cause: error.cause });
    }
}

export async function get_fleets_v3(access_token:string, status:FleetStatus) {
    const headers = {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${access_token}`
    }

    const ENDPOINT = `${API_ENDPOINT}/v3?fleet_filter=${status}`

    console.log(`Requesting: ${ENDPOINT}`)

    try {
        const response = await fetch(ENDPOINT, {
            headers: headers
        })

        // console.log(response)

        if (!response.ok) {
            throw new Error(get_error_message(
                response.status,
                `GET ${ENDPOINT}`
            ), {
                cause: response.status
            });
        }

        return await response.json() as Fleet[];
    } catch (error) {
        throw new Error(`Error fetching fleets: ${error.message}`, { cause: error.cause });
    }
}

export async function create_fleet(access_token:string, fleet:FleetRequest) {
    const data = JSON.stringify(fleet)

    const headers = {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${access_token}`
    }

    const ENDPOINT = API_ENDPOINT

    console.log(`Requesting POST: ${ENDPOINT}`)

    try {
        const response = await fetch(ENDPOINT, {
            headers: headers,
            body: data,
            method: 'POST'
        })

        // console.log(response)

        if (!response.ok) {
            throw new Error(get_error_message(
                response.status,
                `POST ${ENDPOINT}`
            ))
        }

        return await response.json() as Fleet;
    } catch (error) {
        throw new Error(`Error creating fleet: ${error.message}`, { cause: error.cause });
    }
}

export async function update_fleet(access_token:string, fleet:FleetPatchRequest, fleet_id: number) {
    const data = JSON.stringify(fleet)
    
    const headers = {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${access_token}`
    }

    const ENDPOINT = `${API_ENDPOINT}/${fleet_id}`

    console.log(`Requesting PATCH: ${ENDPOINT}`)

    try {
        const response = await fetch(ENDPOINT, {
            headers: headers,
            body: data,
            method: 'PATCH'
        })

        // console.log(response)

        if (!response.ok) {
            throw new Error(get_error_message(
                response.status,
                `POST ${ENDPOINT}`
            ))
        }

        return await response.json() as Fleet;
    } catch (error) {
        throw new Error(`Error updating fleet: ${error.message}`, { cause: error.cause });
    }
}

export async function get_fleet_by_id(access_token:string, id:number) {
    const headers = {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${access_token}`
    }

    const ENDPOINT = `${API_ENDPOINT}/${id}`

    console.log(`Requesting: ${ENDPOINT}`)

    try {
        const response = await fetch(ENDPOINT, {
            headers: headers,
        })

        // console.log(response)

        if (!response.ok) {
            throw new Error(get_error_message(
                response.status,
                `GET ${ENDPOINT}`
            ), {
                cause: response.status
            })
        }

        return await response.json() as Fleet;
    } catch (error) {
        throw new Error(`Error fetching fleet: ${error.message}`, { cause: error.cause });
    }
}

export async function delete_fleet(access_token:string, id:number) {
    const headers = {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${access_token}`
    }

    const ENDPOINT = `${API_ENDPOINT}/${id}`

    console.log(`Requesting DELETE: ${ENDPOINT}`)

    try {
        const response = await fetch(ENDPOINT, {
            headers: headers,
            method: 'DELETE'
        })

        // console.log(response)

        if (!response.ok) {
            throw new Error(get_error_message(
                response.status,
                `DELETE ${ENDPOINT}`
            ), {
                cause: response.status
            });
        }

        return (response.status === 200);
    } catch (error) {
        throw new Error(`Error deleting fleet: ${error.message}`, { cause: error.cause });
    }
}

export async function start_fleet_now(access_token: string, fc_character_id?: number): Promise<Fleet> {
    const headers = {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${access_token}`
    }

    const ENDPOINT = `${API_ENDPOINT}/start-now`
    const body = fc_character_id != null ? JSON.stringify({ fc_character_id }) : undefined

    const response = await fetch(ENDPOINT, {
        headers,
        method: 'POST',
        ...(body != null ? { body } : {})
    })

    if (!response.ok) {
        const err = await parse_response_error(response, `POST ${ENDPOINT}`)
        throw new Error(err)
    }

    return await response.json() as Fleet
}

export async function start_fleet(access_token:string, fleet_id:number) {
    const headers = {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${access_token}`
    }

    const ENDPOINT = `${API_ENDPOINT}/${fleet_id}/tracking`
    const METHOD = 'POST'

    console.log(`Requesting POST: ${ENDPOINT}`)

    try {
        const response = await fetch(ENDPOINT, {
            headers: headers,
            method: METHOD
        })

        // console.log(response)

        if (!response.ok)
            throw new Error(await parse_response_error(response, `${METHOD} ${ENDPOINT}`))
        
        return (response.status === 200);
    } catch (error) {
        throw new Error(`Error starting the fleet: ${error.message}`, { cause: error.cause });
    }
}

export async function get_fleet_members(access_token:string, id:number) {
    const headers = {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${access_token}`
    }

    const ENDPOINT = `${API_ENDPOINT}/${id}/members`

    console.log(`Requesting: ${ENDPOINT}`)

    try {
        const response = await fetch(ENDPOINT, {
            headers: headers,
        })

        // console.log(response)

        if (!response.ok) {
            throw new Error(get_error_message(
                response.status,
                `GET ${ENDPOINT}`
            ), {
                cause: response.status
            });
        }

        return await response.json() as FleetMember[];
    } catch (error) {
        throw new Error(`Error fetching fleet members: ${error.message}`, { cause: error.cause });
    }
}

export async function get_fleet_users(access_token:string, fleet_id:number) {
    const headers = {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${access_token}`,
    }

    const ENDPOINT = `${API_ENDPOINT}/${fleet_id}/users`

    console.log(`Requesting: ${ENDPOINT}`)

    try {
        const response = await fetch(ENDPOINT, {
            headers: headers,
        })

        // console.log(response)

        if (!response.ok) {
            throw new Error(get_error_message(
                response.status,
                `GET ${ENDPOINT}`
            ), {
                cause: response.status
            });
        }

        return await response.json() as FleetUsers[];
    } catch (error) {
        throw new Error(`Error fetching fleet: ${error.message}`, { cause: error.cause });
    }
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
    const headers = {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${access_token}`,
    }
    const ENDPOINT = `${API_ENDPOINT}/${fleet_id}/role-volunteers`
    const response = await fetch(ENDPOINT, { headers })
    if (!response.ok)
        throw new Error(await parse_response_error(response, `GET ${ENDPOINT}`))
    return await response.json() as FleetRoleVolunteer[]
}

export async function create_fleet_role_volunteer(
    access_token: string,
    fleet_id: number,
    payload: { character_id: number; role: string; subtype?: string | null; quantity?: number | null }
): Promise<FleetRoleVolunteer> {
    const headers = {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${access_token}`,
    }
    const ENDPOINT = `${API_ENDPOINT}/${fleet_id}/role-volunteers`
    const response = await fetch(ENDPOINT, {
        method: 'POST',
        headers,
        body: JSON.stringify(payload),
    })
    if (!response.ok)
        throw new Error(await parse_response_error(response, `POST ${ENDPOINT}`))
    return await response.json() as FleetRoleVolunteer
}

export async function delete_fleet_role_volunteer(access_token: string, fleet_id: number, volunteer_id: number): Promise<void> {
    const headers = {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${access_token}`,
    }
    const ENDPOINT = `${API_ENDPOINT}/${fleet_id}/role-volunteers/${volunteer_id}`
    const response = await fetch(ENDPOINT, { method: 'DELETE', headers })
    if (!response.ok && response.status !== 204)
        throw new Error(await parse_response_error(response, `DELETE ${ENDPOINT}`))
}

export async function refresh_fleet_motd(access_token: string, fleet_id: number): Promise<void> {
    const headers = {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${access_token}`,
    }
    const ENDPOINT = `${API_ENDPOINT}/${fleet_id}/refresh-motd`
    const response = await fetch(ENDPOINT, { headers, method: 'POST' })
    if (!response.ok)
        throw new Error(await parse_response_error(response, `POST ${ENDPOINT}`))
}

export async function preping(access_token:string, fleet_id:number) {
    const headers = {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${access_token}`
    }

    const ENDPOINT = `${API_ENDPOINT}/${fleet_id}/preping`
    const METHOD = 'POST'

    console.log(`Requesting ${METHOD}: ${ENDPOINT}`)

    try {
        const response = await fetch(ENDPOINT, {
            headers: headers,
            method: METHOD,
        })

        // console.log(response)

        if (!response.ok)
            throw new Error(await parse_response_error(response, `${METHOD} ${ENDPOINT}`))

        return (response.status === 200)
    } catch (error) {
        throw new Error(`Error creating pre-ping: ${error.message}`, { cause: error.cause });
    }
}

export async function get_fleets_metrics(access_token:string) {
    const headers = {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${access_token}`
    }

    const ENDPOINT = `${API_ENDPOINT}/metrics`

    console.log(`Requesting: ${ENDPOINT}`)

    try {
        const response = await fetch(ENDPOINT, {
            headers: headers
        })

        // console.log(response)

        if (!response.ok) {
            throw new Error(get_error_message(
                response.status,
                `GET ${ENDPOINT}`
            ), {
                cause: response.status
            });
        }

        return await response.json() as FleetMetrics[];
    } catch (error) {
        throw new Error(`Error fetching fleet metrics: ${error.message}`, { cause: error.cause });
    }
}

export async function get_fleet_commander_metrics(access_token:string) {
    const headers = {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${access_token}`
    }

    const ENDPOINT = `${API_ENDPOINT}/commander-metrics`

    console.log(`Requesting: ${ENDPOINT}`)

    try {
        const response = await fetch(ENDPOINT, {
            headers: headers
        })

        // console.log(response)

        if (!response.ok) {
            throw new Error(get_error_message(
                response.status,
                `GET ${ENDPOINT}`
            ), {
                cause: response.status
            });
        }

        return await response.json() as FleetCommanderMetrics[];
    } catch (error) {
        throw new Error(`Error fetching fleet commander metrics: ${error.message}`, { cause: error.cause });
    }
}
// --- Cyno system assignment -------------------------------------------------

export async function assign_fleet_role_volunteer_system(
    access_token: string,
    fleet_id: number,
    volunteer_id: number,
    payload: { solar_system_id: number | null; solar_system_name: string | null }
): Promise<FleetRoleVolunteer> {
    const headers = {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${access_token}`,
    }
    const ENDPOINT = `${API_ENDPOINT}/${fleet_id}/role-volunteers/${volunteer_id}`
    const response = await fetch(ENDPOINT, {
        method: 'PATCH',
        headers,
        body: JSON.stringify(payload),
    })
    if (!response.ok)
        throw new Error(await parse_response_error(response, `PATCH ${ENDPOINT}`))
    return await response.json() as FleetRoleVolunteer
}

// --- Ship volunteers (doctrine composition) ----------------------------------

export interface FleetShipVolunteer {
    id: number
    character_id: number
    character_name: string
    fitting_id: number | null
    fleet_fitting_id: number | null
    fitting_name: string
    ship_id: number
}

// --- Fleet composition (doctrine fits + fleet fittings) ---------------------

export type FleetCompositionSource = 'doctrine' | 'catalog' | 'manual'
export type FleetFittingRole = 'primary' | 'secondary' | 'support'

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
}

export interface MyFleetPilot {
    character_id: number
    character_name: string
    /** Joined a tracked fleet in the last 30 days. */
    recent_fleets: boolean
    selection: ShipSelection | null
}

export async function get_fleet_my_pilots(access_token: string, fleet_id: number): Promise<MyFleetPilot[]> {
    const headers = {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${access_token}`,
    }
    const ENDPOINT = `${API_ENDPOINT}/${fleet_id}/my-pilots`
    const response = await fetch(ENDPOINT, { headers })
    if (!response.ok)
        throw new Error(await parse_response_error(response, `GET ${ENDPOINT}`))
    return await response.json() as MyFleetPilot[]
}

/** Replace the caller's ship volunteers: one ship per listed character, none = not flying. */
export async function set_my_ship_volunteers(access_token: string, fleet_id: number, selections: ShipSelection[]): Promise<FleetShipVolunteer[]> {
    const headers = {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${access_token}`,
    }
    const ENDPOINT = `${API_ENDPOINT}/${fleet_id}/my-ship-volunteers`
    const response = await fetch(ENDPOINT, {
        method: 'PUT',
        headers,
        body: JSON.stringify({ selections }),
    })
    if (!response.ok)
        throw new Error(await parse_response_error(response, `PUT ${ENDPOINT}`))
    return await response.json() as FleetShipVolunteer[]
}

/** A custom EFT fit the caller has used on one of their fleets before. */
export interface MyFleetFitting {
    name: string
    ship_id: number
    ship_name: string
    eft_format: string
}

export async function get_my_fleet_fittings(access_token: string): Promise<MyFleetFitting[]> {
    const headers = {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${access_token}`,
    }
    const ENDPOINT = `${API_ENDPOINT}/my-fittings`
    const response = await fetch(ENDPOINT, { headers })
    if (!response.ok)
        throw new Error(await parse_response_error(response, `GET ${ENDPOINT}`))
    return await response.json() as MyFleetFitting[]
}

export async function get_fleet_supply(access_token: string, fleet_id: number): Promise<FleetSupply> {
    const headers = {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${access_token}`,
    }
    const ENDPOINT = `${API_ENDPOINT}/${fleet_id}/supply`
    const response = await fetch(ENDPOINT, { headers })
    if (!response.ok)
        throw new Error(await parse_response_error(response, `GET ${ENDPOINT}`))
    return await response.json() as FleetSupply
}

/** Payload target for volunteers/refits: catalog fit or manual fleet fit. */
export const composition_target = (entry: FleetCompositionEntry) =>
    entry.fitting_id ? { fitting_id: entry.fitting_id } : { fleet_fitting_id: entry.fleet_fitting_id as number }

export const volunteer_matches_entry = (volunteer: FleetShipVolunteer, entry: FleetCompositionEntry) =>
    entry.fitting_id ? volunteer.fitting_id === entry.fitting_id : volunteer.fleet_fitting_id === entry.fleet_fitting_id

export async function get_fleet_composition(access_token: string, fleet_id: number): Promise<FleetCompositionEntry[]> {
    const headers = {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${access_token}`,
    }
    const ENDPOINT = `${API_ENDPOINT}/${fleet_id}/composition`
    const response = await fetch(ENDPOINT, { headers })
    if (!response.ok)
        throw new Error(await parse_response_error(response, `GET ${ENDPOINT}`))
    return await response.json() as FleetCompositionEntry[]
}

export async function create_fleet_fitting(
    access_token: string,
    fleet_id: number,
    payload: { fitting_id?: number | null; eft_format?: string | null; role?: FleetFittingRole }
): Promise<FleetCompositionEntry> {
    const headers = {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${access_token}`,
    }
    const ENDPOINT = `${API_ENDPOINT}/${fleet_id}/fittings`
    const response = await fetch(ENDPOINT, {
        method: 'POST',
        headers,
        body: JSON.stringify(payload),
    })
    if (!response.ok)
        throw new Error(await parse_response_error(response, `POST ${ENDPOINT}`))
    return await response.json() as FleetCompositionEntry
}

export async function delete_fleet_fitting(access_token: string, fleet_id: number, fleet_fitting_id: number): Promise<void> {
    const headers = {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${access_token}`,
    }
    const ENDPOINT = `${API_ENDPOINT}/${fleet_id}/fittings/${fleet_fitting_id}`
    const response = await fetch(ENDPOINT, { method: 'DELETE', headers })
    if (!response.ok && response.status !== 204)
        throw new Error(await parse_response_error(response, `DELETE ${ENDPOINT}`))
}

export async function get_fleet_ship_volunteers(access_token: string, fleet_id: number): Promise<FleetShipVolunteer[]> {
    const headers = {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${access_token}`,
    }
    const ENDPOINT = `${API_ENDPOINT}/${fleet_id}/ship-volunteers`
    const response = await fetch(ENDPOINT, { headers })
    if (!response.ok)
        throw new Error(await parse_response_error(response, `GET ${ENDPOINT}`))
    return await response.json() as FleetShipVolunteer[]
}


export async function delete_fleet_ship_volunteer(access_token: string, fleet_id: number, volunteer_id: number): Promise<void> {
    const headers = {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${access_token}`,
    }
    const ENDPOINT = `${API_ENDPOINT}/${fleet_id}/ship-volunteers/${volunteer_id}`
    const response = await fetch(ENDPOINT, { method: 'DELETE', headers })
    if (!response.ok && response.status !== 204)
        throw new Error(await parse_response_error(response, `DELETE ${ENDPOINT}`))
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
    const headers = {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${access_token}`,
    }
    const ENDPOINT = `${API_ENDPOINT}/${fleet_id}/fitting-access`
    const response = await fetch(ENDPOINT, { headers })
    if (!response.ok)
        throw new Error(await parse_response_error(response, `GET ${ENDPOINT}`))
    return await response.json() as FleetFittingAccess
}

export async function get_fleet_refits(access_token: string, fleet_id: number): Promise<FleetRefit[]> {
    const headers = {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${access_token}`,
    }
    const ENDPOINT = `${API_ENDPOINT}/${fleet_id}/refits`
    const response = await fetch(ENDPOINT, { headers })
    if (!response.ok)
        throw new Error(await parse_response_error(response, `GET ${ENDPOINT}`))
    return await response.json() as FleetRefit[]
}

export async function create_fleet_refit(access_token: string, fleet_id: number, payload: FleetRefitRequest): Promise<FleetRefit> {
    const headers = {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${access_token}`,
    }
    const ENDPOINT = `${API_ENDPOINT}/${fleet_id}/refits`
    const response = await fetch(ENDPOINT, {
        method: 'POST',
        headers,
        body: JSON.stringify(payload),
    })
    if (!response.ok)
        throw new Error(await parse_response_error(response, `POST ${ENDPOINT}`))
    return await response.json() as FleetRefit
}

export async function delete_fleet_refit(access_token: string, fleet_id: number, refit_id: number): Promise<void> {
    const headers = {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${access_token}`,
    }
    const ENDPOINT = `${API_ENDPOINT}/${fleet_id}/refits/${refit_id}`
    const response = await fetch(ENDPOINT, { method: 'DELETE', headers })
    if (!response.ok && response.status !== 204)
        throw new Error(await parse_response_error(response, `DELETE ${ENDPOINT}`))
}
