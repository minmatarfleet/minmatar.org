import type { Character } from '@dtypes/api.minmatar.org'

const API_ENDPOINT =  `${import.meta.env.API_URL}/api/eveonline`

export async function get_characters(access_token:string) {
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

        return await response.json() as Character[];
    } catch (error) {
        throw new Error(`Error fetching characters: ${error.message}`);
    }
}

export async function get_character_by_id(access_token:string, character_id:number) {
    const headers = {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${access_token}`
    }

    console.log(`Requesting: ${API_ENDPOINT}/characters/${character_id}`)

    try {
        const response = await fetch(`${API_ENDPOINT}/characters/${character_id}`, {
            headers: headers
        })

        console.log(response)

        if (!response.ok) {
            throw new Error(`HTTP error! Status: ${response.status}`);
        }

        return await response.json() as Character;
    } catch (error) {
        throw new Error(`Error fetching character: ${error.message}`);
    }
}

export async function delete_characters(access_token:string, character_id:number) {
    const headers = {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${access_token}`
    }

    console.log(`Requesting DELETE: ${API_ENDPOINT}/characters/${character_id}`)

    try {
        const response = await fetch(`${API_ENDPOINT}/characters/${character_id}`, {
            method: 'DELETE',
            headers: headers
        })

        console.log(response)

        if (!response.ok) {
            throw new Error(`HTTP error! Status: ${response.status}`);
        }

        return (response.status === 200);
    } catch (error) {
        throw new Error(`Error deleting characters: ${error.message}`);
    }
}

export async function get_primary_characters(access_token:string) {
    const headers = {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${access_token}`
    }

    console.log(`Requesting: ${API_ENDPOINT}/characters/primary`)

    try {
        const response = await fetch(`${API_ENDPOINT}/characters/primary`, {
            headers: headers
        })

        console.log(response)

        if (!response.ok) {
            throw new Error(`HTTP error! Status: ${response.status}`);
        }

        return await response.json() as Character;
    } catch (error) {
        throw new Error(`Error fetching main pilot: ${error.message}`);
    }
}