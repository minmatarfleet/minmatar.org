import type { FleetMember, Fleet, FleetRequest, Audience } from '@dtypes/api.minmatar.org'
import { get_error_message } from '@helpers/string'

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
            throw new Error(await get_error_message(
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

    const ENDPOINT = `${API_ENDPOINT}/locations`

    console.log(`Requesting: ${ENDPOINT}`)

    try {
        const response = await fetch(ENDPOINT, {
            headers: headers
        })

        // console.log(response)

        if (!response.ok) {
            throw new Error(await get_error_message(
                response.status,
                `GET ${ENDPOINT}`
            ));
        }

        return await response.json() as string[];
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
            throw new Error(await get_error_message(
                response.status,
                `GET ${ENDPOINT}`
            ));
        }

        return await response.json() as Audience[];
    } catch (error) {
        throw new Error(`Error fetching fleet types: ${error.message}`);
    }
}

export async function get_fleets(access_token:string, upcoming:boolean = true) {
    const headers = {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${access_token}`
    }

    const ENDPOINT = `${API_ENDPOINT}?upcoming=${JSON.stringify(upcoming)}`

    console.log(`Requesting: ${ENDPOINT}`)

    try {
        const response = await fetch(ENDPOINT, {
            headers: headers
        })

        // console.log(response)

        if (!response.ok) {
            throw new Error(await get_error_message(
                response.status,
                `GET ${ENDPOINT}`
            ));
        }

        return await response.json() as number[];
    } catch (error) {
        throw new Error(`Error fetching fleets: ${error.message}`);
    }
}

export async function create_fleet(access_token:string, fleet:FleetRequest) {
    const data = JSON.stringify(fleet);

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
            throw new Error(await get_error_message(
                response.status,
                `POST ${ENDPOINT}`
            ))
        }

        return await response.json() as FleetRequest;
    } catch (error) {
        throw new Error(`Error fetching creating fleet: ${error.message}`);
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
            throw new Error(await get_error_message(
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

        console.log(response)

        if (!response.ok) {
            throw new Error(await get_error_message(
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

    console.log(`Requesting POST: ${ENDPOINT}`)

    try {
        const response = await fetch(ENDPOINT, {
            headers: headers,
            method: 'POST'
        })

        console.log(response)

        if (!response.ok) {
            const error = await response.json()
            console.log(error)

            throw new Error(await get_error_message(
                error?.detail ? error?.detail : response.status,
                `POST ${ENDPOINT}`
            ))
        }
        
        return (response.status === 200);
    } catch (error) {
        throw new Error(`Error fetching creating fleet: ${error.message}`);
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
            throw new Error(await get_error_message(
                response.status,
                `GET ${ENDPOINT}`
            ))
        }

        return await response.json() as FleetMember[];
    } catch (error) {
        throw new Error(`Error fetching fleet: ${error.message}`);
    }
}