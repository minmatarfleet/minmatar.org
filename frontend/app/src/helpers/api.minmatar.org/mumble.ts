import type { MumbleInformation } from '@dtypes/api.minmatar.org'

const API_ENDPOINT = `${import.meta.env.API_URL}/api/mumble`

export async function get_mumble_connection(access_token:string) {
    const headers = {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${access_token}`
    }

    console.log(`Requesting: ${API_ENDPOINT}/connection`)

    try {
        const response = await fetch(`${API_ENDPOINT}/connection`, {
            headers: headers
        })

        console.log(response)

        if (!response.ok) {
            throw new Error(`HTTP error! Status: ${response.status}`);
        }

        return await response.json() as MumbleInformation;
    } catch (error) {
        throw new Error(`Error fetching mumble connection information: ${error.message}`);
    }
}