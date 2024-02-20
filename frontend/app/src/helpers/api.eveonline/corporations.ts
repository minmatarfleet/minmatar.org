import type { CorporationEvE } from '@dtypes/api.eveonline'

const API_ENDPOINT =  `${import.meta.env.EVE_API_URL ?? 'https://esi.evetech.net/latest'}/corporations`

export async function get_corporation_by_id(id:number) {
    const headers = {
        'Content-Type': 'application/json',
    }

    console.log(`Requesting: ${API_ENDPOINT}/${id}`)

    try {
        const response = await fetch(`${API_ENDPOINT}/${id}`, {
            headers: headers
        })

        console.log(response)

        if (!response.ok) {
            throw new Error(`HTTP error! Status: ${response.status}`);
        }

        return await response.json() as CorporationEvE;
    } catch (error) {
        throw new Error(`Error fetching character: ${error.message}`);
    }
}