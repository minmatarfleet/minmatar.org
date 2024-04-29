import type { FleetTypes, Fleet, FleetRequest, Audience } from '@dtypes/api.minmatar.org'

const API_ENDPOINT = `${import.meta.env.API_URL}/api/fleets`

export async function get_types(access_token:string) {
    const headers = {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${access_token}`
    }

    console.log(`Requesting: ${API_ENDPOINT}/types`)

    try {
        const response = await fetch(`${API_ENDPOINT}/types`, {
            headers: headers
        })

        // console.log(response)

        if (!response.ok) {
            throw new Error(`HTTP error! Status: ${response.status}`);
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

    console.log(`Requesting: ${API_ENDPOINT}/locations`)

    try {
        const response = await fetch(`${API_ENDPOINT}/locations`, {
            headers: headers
        })

        // console.log(response)

        if (!response.ok) {
            throw new Error(`HTTP error! Status: ${response.status}`);
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

    console.log(`Requesting: ${API_ENDPOINT}/audiences`)

    try {
        const response = await fetch(`${API_ENDPOINT}/audiences`, {
            headers: headers
        })

        // console.log(response)

        if (!response.ok) {
            throw new Error(`HTTP error! Status: ${response.status}`);
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

    console.log(`Requesting: ${API_ENDPOINT}?upcoming=${JSON.stringify(upcoming)}`)

    try {
        const response = await fetch(`${API_ENDPOINT}?upcoming=${JSON.stringify(upcoming)}`, {
            headers: headers
        })

        // console.log(response)

        if (!response.ok) {
            throw new Error(`HTTP error! Status: ${response.status}`);
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

    console.log(`Requesting POST: ${API_ENDPOINT}`)

    try {
        const response = await fetch(`${API_ENDPOINT}`, {
            headers: headers,
            body: data,
            method: 'POST'
        })

        // console.log(response)

        if (!response.ok) {
            throw new Error(`HTTP error! Status: ${response.status}`);
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

    console.log(`Requesting: ${API_ENDPOINT}/${id}`)

    try {
        const response = await fetch(`${API_ENDPOINT}/${id}`, {
            headers: headers,
        })

        // console.log(response)

        if (!response.ok) {
            throw new Error(`HTTP error! Status: ${response.status}`);
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

    console.log(`Requesting DELETE: ${API_ENDPOINT}/${id}`)

    try {
        const response = await fetch(`${API_ENDPOINT}/${id}`, {
            headers: headers,
            method: 'DELETE'
        })

        console.log(response)

        if (!response.ok) {
            throw new Error(`HTTP error! Status: ${response.status}`);
        }

        return (response.status === 200);
    } catch (error) {
        throw new Error(`Error deleting fleet: ${error.message}`);
    }
}