import type { Character, CharacterSkillset, CharacterAsset } from '@dtypes/api.minmatar.org'

const API_ENDPOINT =  `${import.meta.env.API_URL}/api/eveonline/characters`

export async function get_characters(access_token:string) {
    const headers = {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${access_token}`
    }

    console.log(`Requesting: ${API_ENDPOINT}`)

    try {
        const response = await fetch(`${API_ENDPOINT}`, {
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

    console.log(`Requesting: ${API_ENDPOINT}/${character_id}`)

    try {
        const response = await fetch(`${API_ENDPOINT}/${character_id}`, {
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

    console.log(`Requesting DELETE: ${API_ENDPOINT}/${character_id}`)

    try {
        const response = await fetch(`${API_ENDPOINT}/${character_id}`, {
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

    console.log(`Requesting: ${API_ENDPOINT}/primary`)

    try {
        const response = await fetch(`${API_ENDPOINT}/primary`, {
            headers: headers
        })

        console.log(response)

        if (response.status != 200 && response.status != 404) {
            throw new Error(`HTTP error! Status: ${response.status}`);
        }

        return await response.json() as Character;
    } catch (error) {
        throw new Error(`Error fetching main pilot: ${error.message}`);
    }
}

export async function get_character_skillsets(access_token:string, character_id:number) {
    const headers = {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${access_token}`
    }

    console.log(`Requesting: ${API_ENDPOINT}/${character_id}/skillsets`)

    try {
        const response = await fetch(`${API_ENDPOINT}/${character_id}/skillsets`, {
            headers: headers
        })

        console.log(response)

        if (!response.ok) {
            throw new Error(`HTTP error! Status: ${response.status}`);
        }

        return await response.json() as CharacterSkillset[];
    } catch (error) {
        throw new Error(`Error fetching character skillsets: ${error.message}`);
    }
}

export async function get_character_assets(access_token:string, character_id:number) {
    const headers = {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${access_token}`
    }

    console.log(`Requesting: ${API_ENDPOINT}/${character_id}/assets`)

    try {
        const response = await fetch(`${API_ENDPOINT}/${character_id}/assets`, {
            headers: headers
        })

        console.log(response)

        if (!response.ok) {
            throw new Error(`HTTP error! Status: ${response.status}`);
        }

        return await response.json() as CharacterAsset[];
    } catch (error) {
        throw new Error(`Error fetching character assets: ${error.message}`);
    }
}