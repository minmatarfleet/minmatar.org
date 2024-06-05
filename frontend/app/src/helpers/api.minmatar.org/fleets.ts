import type { FleetMember, Fleet, FleetRequest, Audience, Location } from '@dtypes/api.minmatar.org'
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
            throw new Error(get_error_message(
                response.status,
                `POST ${ENDPOINT}`
            ))
        }

        return await response.json() as Fleet;
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

    console.log(`Requesting POST: ${ENDPOINT}`)

    try {
        const response = await fetch(ENDPOINT, {
            headers: headers,
            method: 'POST'
        })

        // console.log(response)

        if (!response.ok) {
            let error = await response.json()
            const error_msg = parse_error_message(error.detail)
            error = error_msg ? error_msg : error?.detail

            throw new Error(error ? error : get_error_message(response.status, `POST ${ENDPOINT}`))
        }
        
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

const parse_error_message = (error_details:string) => {
    // Regular expression to match the error message inside the single quotes after "error": 
    const regex = /'error': '([^']+)'/;
    const match = error_details.match(regex);
    
    if (match && match[1]) {
        return match[1];
    } else {
        return null; // or handle the case when the pattern doesn't match
    }
}