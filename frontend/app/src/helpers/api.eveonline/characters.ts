import type { CharacterEvE, CorporationHistoryEvE } from '@dtypes/api.eveonline'

const API_ENDPOINT =  `${import.meta.env.EVE_API_URL ?? 'https://esi.evetech.net/latest'}/characters`

export async function get_character_by_id(character_id:number) {
    const headers = {
        'Content-Type': 'application/json',
    }

    console.log(`Requesting: ${API_ENDPOINT}/${character_id}`)

    try {
        const response = await fetch(`${API_ENDPOINT}/${character_id}`, {
            headers: headers
        })

        console.log(response)

        if (!response.ok) {
            throw new Error(`HTTP error! Status: ${response.status}`);
        }

        return await response.json() as CharacterEvE;
    } catch (error) {
        throw new Error(`Error fetching character: ${error.message}`);
    }
}

export async function get_corporation_history(character_id:number) {
    const headers = {
        'Content-Type': 'application/json',
    }

    console.log(`Requesting: ${API_ENDPOINT}/${character_id}/corporationhistory/`)

    try {
        const response = await fetch(`${API_ENDPOINT}/${character_id}/corporationhistory/`, {
            headers: headers
        })

        console.log(response)

        if (!response.ok) {
            throw new Error(`HTTP error! Status: ${response.status}`);
        }

        return await response.json() as CorporationHistoryEvE[];
    } catch (error) {
        throw new Error(`Error fetching corporation history: ${error.message}`);
    }
}