import type { Character } from '@dtypes/api.minmatar.org'

const API_ENDPOINT = import.meta.env.MINMATAR_API_ENDPOINT

export async function get_characters(access_token:string):Character[] {
    const headers = {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${access_token}`
    }

    console.log(`Requesting: ${API_ENDPOINT}/characters`)

    try {
        const response = await fetch(`${API_ENDPOINT}/characters`, {
            headers: headers
        })

        console.log(response)

        if (!response.ok) {
            throw new Error(`HTTP error! Status: ${response.status}`);
        }

        const json = await response.json();
        return json;
    } catch (error) {
        throw new Error(`Error getting characters: ${error.message}`);
    }
}