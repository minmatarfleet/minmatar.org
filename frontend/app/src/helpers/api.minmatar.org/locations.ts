import type { Location } from '@dtypes/api.minmatar.org'
import { get_error_message } from '@helpers/string'

const API_ENDPOINT = `${import.meta.env.API_URL}/api/eveonline/locations`

export async function get_locations() {
    const headers = {
        'Content-Type': 'application/json',
    }

    const ENDPOINT = `${API_ENDPOINT}/`

    console.log(`Requesting: ${ENDPOINT}`)

    try {
        const response = await fetch(ENDPOINT, {
            headers: headers
        })

        if (!response.ok) {
            throw new Error(get_error_message(
                response.status,
                `GET ${ENDPOINT}`
            ));
        }

        return await response.json() as Location[];
    } catch (error) {
        throw new Error(`Error fetching locations: ${error.message}`);
    }
}

export async function get_locations_by_ids(location_ids: number[]) {
    const headers = {
        'Content-Type': 'application/json',
    }

    const ids_string = location_ids.join(',')
    const ENDPOINT = `${API_ENDPOINT}/by-ids?location_ids=${ids_string}`

    console.log(`Requesting: ${ENDPOINT}`)

    try {
        const response = await fetch(ENDPOINT, {
            headers: headers
        })

        if (!response.ok) {
            throw new Error(get_error_message(
                response.status,
                `GET ${ENDPOINT}`
            ));
        }

        return await response.json() as Location[];
    } catch (error) {
        throw new Error(`Error fetching locations by IDs: ${error.message}`);
    }
}

