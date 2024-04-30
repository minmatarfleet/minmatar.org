import type { MumbleInformation } from '@dtypes/api.minmatar.org'
import { get_error_message } from '@helpers/string'

const API_ENDPOINT = `${import.meta.env.API_URL}/api/mumble`

export async function get_mumble_connection(access_token:string) {
    const headers = {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${access_token}`
    }

    const ENDPOINT = `${API_ENDPOINT}/connection`

    console.log(`Requesting: ${ENDPOINT}`)

    try {
        const response = await fetch(ENDPOINT, {
            headers: headers
        })

        console.log(response)

        if (!response.ok) {
            throw new Error(await get_error_message(
                response.status,
                `GET ${ENDPOINT}`
            ))
        }

        return await response.json() as MumbleInformation;
    } catch (error) {
        throw new Error(`Error fetching mumble connection information: ${error.message}`);
    }
}