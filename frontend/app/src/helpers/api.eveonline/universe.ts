import type { NamesAndCategoriesEvE } from '@dtypes/api.eveonline'

const API_ENDPOINT =  `${import.meta.env.EVE_API_URL ?? 'https://esi.evetech.net/latest'}/universe`

export async function get_names_and_categories_by_ids(ids:number[]) {
    const headers = {
        'Content-Type': 'application/json',
    }

    console.log(`Requesting: ${API_ENDPOINT}/names/`)

    try {
        const response = await fetch(`${API_ENDPOINT}/names/`, {
            headers: headers,
            method: 'POST',
            body: JSON.stringify(ids),
        })

        console.log(response)

        if (!response.ok) {
            throw new Error(`HTTP error! Status: ${response.status}`);
        }

        return await response.json() as NamesAndCategoriesEvE[];
    } catch (error) {
        throw new Error(`Error fetching names and categories: ${error.message}`);
    }
}