import type {
    Character,
    CharacterSkillset,
    CharacterAsset,
    CharacterSummary,
    CharacterESITokens,
    CharacterTag
} from '@dtypes/api.minmatar.org'
import { get_error_message } from '@helpers/string'

const API_ENDPOINT =  `${import.meta.env.API_URL}/api/eveonline/characters`

export async function get_characters(access_token:string, primary_character_id:number | null = null) {
    const headers = {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${access_token}`
    }

    const ENDPOINT = `${API_ENDPOINT}${primary_character_id ? `?primary_character_id=${primary_character_id}` : ''}`

    console.log(`Requesting: ${ENDPOINT}`)

    try {
        const response = await fetch(ENDPOINT, {
            headers: headers
        })

        // console.log(response)

        if (!response.ok) {
            throw new Error(get_error_message(
                response.status,
                `GET ${ENDPOINT}`
            ), {
                cause: response.status
            });
        }

        return await response.json() as Character[];
    } catch (error) {
        throw new Error(`Error fetching characters: ${error.message}`, { cause: error.cause });
    }
}

export async function get_character_by_id(access_token:string, character_id:number) {
    const headers = {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${access_token}`
    }

    const ENDPOINT = `${API_ENDPOINT}/${character_id}`

    console.log(`Requesting: ${ENDPOINT}`)

    try {
        const response = await fetch(ENDPOINT, {
            headers: headers
        })

        // console.log(response)

        if (!response.ok) {
            throw new Error(get_error_message(
                response.status,
                `GET ${ENDPOINT}`
            ), {
                cause: response.status
            });
        }

        return await response.json() as Character;
    } catch (error) {
        throw new Error(`Error fetching character: ${error.message}`, { cause: error.cause });
    }
}

export async function delete_characters(access_token:string, character_id:number) {
    const headers = {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${access_token}`
    }

    const ENDPOINT = `${API_ENDPOINT}/${character_id}`

    console.log(`Requesting DELETE: ${ENDPOINT}`)

    try {
        const response = await fetch(ENDPOINT, {
            method: 'DELETE',
            headers: headers
        })

        // console.log(response)

        if (!response.ok) {
            throw new Error(get_error_message(
                response.status,
                `DELETE ${ENDPOINT}`
            ), {
                cause: response.status
            });
        }

        return (response.status === 200);
    } catch (error) {
        throw new Error(`Error deleting characters: ${error.message}`, { cause: error.cause });
    }
}

export async function get_primary_characters(access_token:string) {
    const headers = {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${access_token}`
    }

    const ENDPOINT = `${API_ENDPOINT}/primary`

    console.log(`Requesting: ${ENDPOINT}`)

    try {
        const response = await fetch(ENDPOINT, {
            headers: headers
        })

        // console.log(response)

        if (response.status != 200 && response.status != 404) {
            throw new Error(get_error_message(
                response.status,
                `GET ${ENDPOINT}`
            ), {
                cause: response.status
            });
        }

        return await response.json() as Character;
    } catch (error) {
        throw new Error(`Error fetching main pilot: ${error.message}`, { cause: error.cause });
    }
}

/** Resolve main pilot for claim UI without failing the parent page load. */
export type PrimaryClaimAvailability = 'ok' | 'login' | 'auth' | 'no_primary'

export async function resolve_primary_for_claim(
    access_token: string | false
): Promise<{ character_id: number; availability: PrimaryClaimAvailability }> {
    if (!access_token) {
        return { character_id: 0, availability: 'login' }
    }

    try {
        const primary_pilot = await get_primary_characters(access_token)
        const character_id = primary_pilot?.character_id ?? 0

        if (!character_id) {
            return { character_id: 0, availability: 'no_primary' }
        }

        return { character_id, availability: 'ok' }
    } catch {
        return { character_id: 0, availability: 'auth' }
    }
}

export async function get_character_skillsets(access_token:string, character_id:number) {
    const headers = {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${access_token}`
    }

    const ENDPOINT = `${API_ENDPOINT}/${character_id}/skillsets`

    console.log(`Requesting: ${ENDPOINT}`)

    try {
        const response = await fetch(ENDPOINT, {
            headers: headers
        })

        // console.log(response)

        if (!response.ok) {
            throw new Error(get_error_message(
                response.status,
                `GET ${ENDPOINT}`
            ), {
                cause: response.status
            });
        }

        return await response.json() as CharacterSkillset[];
    } catch (error) {
        throw new Error(`Error fetching character skillsets: ${error.message}`, { cause: error.cause });
    }
}

export async function get_character_assets(access_token:string, character_id:number) {
    const headers = {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${access_token}`
    }

    const ENDPOINT = `${API_ENDPOINT}/${character_id}/assets`

    console.log(`Requesting: ${ENDPOINT}`)

    try {
        const response = await fetch(ENDPOINT, {
            headers: headers
        })

        // console.log(response)

        if (!response.ok) {
            throw new Error(get_error_message(
                response.status,
                `GET ${ENDPOINT}`
            ), {
                cause: response.status
            });
        }

        return await response.json() as CharacterAsset[];
    } catch (error) {
        throw new Error(`Error fetching character assets: ${error.message}`, { cause: error.cause });
    }
}

export async function set_primary_characters(access_token:string, character_id:number) {
    const headers = {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${access_token}`
    }

    const ENDPOINT = `${API_ENDPOINT}/primary?character_id=${character_id}`

    console.log(`Requesting PUT: ${ENDPOINT}`)

    try {
        const response = await fetch(ENDPOINT, {
            method: 'PUT',
            headers: headers
        })

        // console.log(response)

        if (!response.ok) {
            throw new Error(get_error_message(
                response.status,
                `PUT ${ENDPOINT}`
            ), {
                cause: response.status
            });
        }

        return (response.status === 200);
    } catch (error) {
        throw new Error(`Error setting main character: ${error.message}`, { cause: error.cause });
    }
}

export async function get_characters_summary(access_token:string) {
    const headers = {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${access_token}`
    }

    const ENDPOINT = `${API_ENDPOINT}/summary`

    console.log(`Requesting: ${ENDPOINT}`)

    try {
        const response = await fetch(ENDPOINT, {
            headers: headers
        })

        // console.log(response)

        if (!response.ok) {
            throw new Error(get_error_message(
                response.status,
                `GET ${ENDPOINT}`
            ), {
                cause: response.status
            });
        }

        return await response.json() as CharacterSummary;
    } catch (error) {
        throw new Error(`Error fetching character summary: ${error.message}`, { cause: error.cause });
    }
}

export async function get_character_esi_token(access_token:string, character_id:number) {
    const headers = {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${access_token}`
    }

    const ENDPOINT = `${API_ENDPOINT}/${character_id}/tokens`

    console.log(`Requesting: ${ENDPOINT}`)

    try {
        const response = await fetch(ENDPOINT, {
            headers: headers
        })

        // console.log(response)

        if (!response.ok) {
            throw new Error(get_error_message(
                response.status,
                `GET ${ENDPOINT}`
            ), {
                cause: response.status
            });
        }

        return await response.json() as CharacterESITokens[];
    } catch (error) {
        throw new Error(`Error fetching character summary: ${error.message}`, { cause: error.cause });
    }
}

export async function get_tags(access_token:string) {
    const headers = {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${access_token}`
    }

    const ENDPOINT = `${API_ENDPOINT}/tags`

    console.log(`Requesting: ${ENDPOINT}`)

    try {
        const response = await fetch(ENDPOINT, {
            headers: headers
        })

        // console.log(response)

        if (!response.ok) {
            throw new Error(get_error_message(
                response.status,
                `GET ${ENDPOINT}`
            ), {
                cause: response.status
            });
        }

        return await response.json() as CharacterTag[];
    } catch (error) {
        throw new Error(`Error fetching character summary: ${error.message}`, { cause: error.cause });
    }
}

export async function set_character_tags(access_token:string, character_id:number, tags:number[]) {
    const headers = {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${access_token}`
    }

    const ENDPOINT = `${API_ENDPOINT}/${character_id}/tags`

    console.log(`Requesting PUT: ${ENDPOINT}`)

    try {
        const response = await fetch(ENDPOINT, {
            method: 'PUT',
            headers: headers,
            body: JSON.stringify(tags),
        })

        // console.log(response)

        if (!response.ok) {
            throw new Error(get_error_message(
                response.status,
                `PUT ${ENDPOINT}`
            ), {
                cause: response.status
            });
        }

        return (response.status === 200);
    } catch (error) {
        throw new Error(`Error setting character tags: ${error.message}`, { cause: error.cause });
    }
}

export async function get_character_tags(access_token:string, character_id:number) {
    const headers = {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${access_token}`
    }

    const ENDPOINT = `${API_ENDPOINT}/${character_id}/tags`

    console.log(`Requesting: ${ENDPOINT}`)

    try {
        const response = await fetch(ENDPOINT, {
            headers: headers
        })

        // console.log(response)

        if (!response.ok) {
            throw new Error(get_error_message(
                response.status,
                `GET ${ENDPOINT}`
            ), {
                cause: response.status
            });
        }

        return await response.json() as CharacterTag[];
    } catch (error) {
        throw new Error(`Error fetching character summary: ${error.message}`, { cause: error.cause });
    }
}