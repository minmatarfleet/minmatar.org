import type {
    FleetMember,
    Fleet,
    FleetRequest,
    Audience,
    Location,
    FleetBasic,
    FleetUsers,
    FleetStatus,
    FleetPatchRequest
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
            ));
        }

        return await response.json() as string[];
    } catch (error) {
        throw new Error(`Error fetching fleet types: ${error.message}`);
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
            throw new Error(get_error_message(
                response.status,
                `GET ${ENDPOINT}`
            ));
        }

        return await response.json() as Location[];
    } catch (error) {
        throw new Error(`Error fetching fleet types: ${error.message}`);
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
            throw new Error(get_error_message(
                response.status,
                `GET ${ENDPOINT}`
            ));
        }

        return await response.json() as Audience[];
    } catch (error) {
        throw new Error(`Error fetching fleet types: ${error.message}`);
    }
}

export async function get_fleets(upcoming:boolean = true) {
    const headers = {
        'Content-Type': 'application/json',
    }

    const ENDPOINT = `${API_ENDPOINT}?upcoming=${JSON.stringify(upcoming)}&active=${JSON.stringify(upcoming)}`

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
            ));
        }

        return await response.json() as number[];
    } catch (error) {
        throw new Error(`Error fetching fleets: ${error.message}`);
    }
}

export async function get_fleets_v2(upcoming:boolean = true) {
    const headers = {
        'Content-Type': 'application/json',
    }

    const ENDPOINT = `${API_ENDPOINT}/v2?upcoming=${JSON.stringify(upcoming)}&active=${JSON.stringify(upcoming)}`

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
            ));
        }

        return await response.json() as FleetBasic[];
    } catch (error) {
        throw new Error(`Error fetching fleets: ${error.message}`);
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
            ));
        }

        return await response.json() as Fleet[];
    } catch (error) {
        throw new Error(`Error fetching fleets: ${error.message}`);
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
        throw new Error(`Error creating fleet: ${error.message}`);
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
        throw new Error(`Error updating fleet: ${error.message}`);
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
            ))
        }

        return await response.json() as Fleet;
    } catch (error) {
        throw new Error(`Error fetching fleet: ${error.message}`);
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
            ))
        }

        return (response.status === 200);
    } catch (error) {
        throw new Error(`Error deleting fleet: ${error.message}`);
    }
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
        throw new Error(`Error starting the fleet: ${error.message}`);
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
            ))
        }

        return await response.json() as FleetMember[];
    } catch (error) {
        throw new Error(`Error fetching fleet members: ${error.message}`);
    }
}

export async function get_fleet_users(fleet_id:number) {
    const headers = {
        'Content-Type': 'application/json',
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
            ))
        }

        return await response.json() as FleetUsers[];
    } catch (error) {
        throw new Error(`Error fetching fleet: ${error.message}`);
    }
}

export interface FleetRoleVolunteer {
    id: number
    character_id: number
    character_name: string
    role: string
    subtype: string | null
    quantity: number | null
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
        throw new Error(`Error creating pre-ping: ${error.message}`);
    }
}