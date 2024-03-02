import type { AllianceEvE } from '@dtypes/api.eveonline'

const API_ENDPOINT =  `${import.meta.env.EVE_API_URL ?? 'https://esi.evetech.net/latest'}/alliances`

export async function get_alliance_by_id(id:number) {
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

        return await response.json() as AllianceEvE;
    } catch (error) {
        throw new Error(`Error fetching alliance: ${error.message}`);
    }
}

export async function get_alliance_corporations(id:number) {
    const headers = {
        'Content-Type': 'application/json',
    }

    console.log(`Requesting: ${API_ENDPOINT}/${id}/corporations`)

    try {
        const response = await fetch(`${API_ENDPOINT}/${id}/corporations`, {
            headers: headers
        })

        console.log(response)

        if (!response.ok) {
            throw new Error(`HTTP error! Status: ${response.status}`);
        }

        return await response.json() as number[];
    } catch (error) {
        throw new Error(`Error fetching alliance corporations: ${error.message}`);
    }
}