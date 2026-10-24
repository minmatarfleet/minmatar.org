import type {
    Character,
    CharacterSkillset,
    CharacterAsset,
    CharacterSummary,
    CharacterESITokens,
    CharacterTag
} from '@dtypes/api.minmatar.org'
import { api_request, api_response, api_status_is } from '@helpers/api.minmatar.org/client'

const API_ENDPOINT =  `${import.meta.env.API_URL}/api/eveonline/characters`

export async function get_characters(access_token:string, primary_character_id:number | null = null) {
    const ENDPOINT = `${API_ENDPOINT}${primary_character_id ? `?primary_character_id=${primary_character_id}` : ''}`

    return await api_request<Character[]>(ENDPOINT, {
        token: access_token,
        error: 'Error fetching characters',
    })
}

export async function get_character_by_id(access_token:string, character_id:number) {
    return await api_request<Character>(`${API_ENDPOINT}/${character_id}`, {
        token: access_token,
        error: 'Error fetching character',
    })
}

export async function delete_characters(access_token:string, character_id:number) {
    return await api_status_is(`${API_ENDPOINT}/${character_id}`, {
        method: 'DELETE',
        token: access_token,
        error: 'Error deleting characters',
    })
}

export async function get_primary_characters(access_token:string) {
    const ENDPOINT = `${API_ENDPOINT}/primary`

    try {
        const response = await api_response(ENDPOINT, {
            token: access_token,
            allow: [404],
        })

        if (response.status != 200 && response.status != 404) {
            throw new Error(`HTTP error! Status — ${response.status}`, {
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
    return await api_request<CharacterSkillset[]>(`${API_ENDPOINT}/${character_id}/skillsets`, {
        token: access_token,
        error: 'Error fetching character skillsets',
    })
}

export async function get_character_assets(access_token:string, character_id:number) {
    return await api_request<CharacterAsset[]>(`${API_ENDPOINT}/${character_id}/assets`, {
        token: access_token,
        error: 'Error fetching character assets',
    })
}

export async function set_primary_characters(access_token:string, character_id:number) {
    return await api_status_is(`${API_ENDPOINT}/primary?character_id=${character_id}`, {
        method: 'PUT',
        token: access_token,
        error: 'Error setting main character',
    })
}

export async function get_characters_summary(access_token:string) {
    return await api_request<CharacterSummary>(`${API_ENDPOINT}/summary`, {
        token: access_token,
        error: 'Error fetching character summary',
    })
}

export async function get_character_esi_token(access_token:string, character_id:number) {
    return await api_request<CharacterESITokens[]>(`${API_ENDPOINT}/${character_id}/tokens`, {
        token: access_token,
        error: 'Error fetching character summary',
    })
}

export async function get_tags(access_token:string) {
    return await api_request<CharacterTag[]>(`${API_ENDPOINT}/tags`, {
        token: access_token,
        error: 'Error fetching character summary',
    })
}

export async function set_character_tags(access_token:string, character_id:number, tags:number[]) {
    return await api_status_is(`${API_ENDPOINT}/${character_id}/tags`, {
        method: 'PUT',
        token: access_token,
        body: tags,
        error: 'Error setting character tags',
    })
}

export async function get_character_tags(access_token:string, character_id:number) {
    return await api_request<CharacterTag[]>(`${API_ENDPOINT}/${character_id}/tags`, {
        token: access_token,
        error: 'Error fetching character summary',
    })
}
/**
 * Sets one of the caller's characters' in-game destination. Resolves to the
 * HTTP status: 204 set, 409 the token lacks esi-ui.write_waypoint.v1,
 * 429 too many clicks, anything else a failure.
 */
export async function set_character_waypoint(access_token:string, character_id:number, destination_id:number) {
    const response = await api_response(`${API_ENDPOINT}/${character_id}/waypoint`, {
        method: 'POST',
        token: access_token,
        body: { destination_id, clear_other_waypoints: true },
        allow: [400, 404, 409, 429, 502],
    })
    return response.status
}
