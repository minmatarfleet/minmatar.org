import type {
    Tribe,
    TribeGroup,
    TribeMembership,
    TribeAvailableCharacter,
    TribeGroupRosterEntry,
    TribeGroupGrowth,
    TribeGroupShowcase,
    CharacterMembership,
} from '@dtypes/api.minmatar.org'
import { get_error_message, query_string } from '@helpers/string'

const API_ENDPOINT = `${import.meta.env.API_URL}/api/tribes`

export async function get_tribes(): Promise<Tribe[]> {
    const ENDPOINT = API_ENDPOINT
    console.log(`Requesting: ${ENDPOINT}`)
    try {
        const response = await fetch(ENDPOINT, {
            headers: { 'Content-Type': 'application/json' },
        })
        if (!response.ok)
            throw new Error(get_error_message(response.status, `GET ${ENDPOINT}`), {
                cause: response.status
            })
        return await response.json() as Tribe[]
    } catch (error) {
        throw new Error(`Error fetching tribes: ${error.message}`)
    }
}

export async function get_current_tribes(access_token: string): Promise<Tribe[]> {
    const ENDPOINT = `${API_ENDPOINT}/current`
    console.log(`Requesting: ${ENDPOINT}`)
    try {
        const response = await fetch(ENDPOINT, {
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${access_token}`,
            },
        })
        if (!response.ok)
            throw new Error(get_error_message(response.status, `GET ${ENDPOINT}`), {
                cause: response.status
            })
        return await response.json() as Tribe[]
    } catch (error) {
        throw new Error(`Error fetching current tribes: ${error.message}`, { cause: error.cause })
    }
}

export async function get_tribe(id: number): Promise<Tribe> {
    const ENDPOINT = `${API_ENDPOINT}/${id}`
    console.log(`Requesting: ${ENDPOINT}`)
    try {
        const response = await fetch(ENDPOINT, {
            headers: { 'Content-Type': 'application/json' },
        })
        if (!response.ok)
            throw new Error(get_error_message(response.status, `GET ${ENDPOINT}`), {
                cause: response.status
            })
        return await response.json() as Tribe
    } catch (error) {
        throw new Error(`Error fetching tribe: ${error.message}`, { cause: error.cause })
    }
}

export async function get_tribe_groups(
    tribe_id: number,
    access_token?: string | false | null,
): Promise<TribeGroup[]> {
    const ENDPOINT = `${API_ENDPOINT}/${tribe_id}/groups`
    console.log(`Requesting: ${ENDPOINT}`)
    try {
        const headers: Record<string, string> = {
            'Content-Type': 'application/json',
        }
        if (access_token)
            headers['Authorization'] = `Bearer ${access_token}`
        const response = await fetch(ENDPOINT, { headers })
        if (!response.ok)
            throw new Error(get_error_message(response.status, `GET ${ENDPOINT}`), {
                cause: response.status
            })
        return await response.json() as TribeGroup[]
    } catch (error) {
        throw new Error(`Error fetching tribe groups: ${error.message}`, { cause: error.cause })
    }
}

export async function get_tribe_group(
    tribe_id: number,
    group_id: number,
    access_token?: string | false | null,
): Promise<TribeGroup> {
    const ENDPOINT = `${API_ENDPOINT}/${tribe_id}/groups/${group_id}`
    console.log(`Requesting: ${ENDPOINT}`)
    try {
        const headers: Record<string, string> = {
            'Content-Type': 'application/json',
        }
        if (access_token)
            headers['Authorization'] = `Bearer ${access_token}`
        const response = await fetch(ENDPOINT, { headers })
        if (!response.ok)
            throw new Error(get_error_message(response.status, `GET ${ENDPOINT}`), {
                cause: response.status
            })
        return await response.json() as TribeGroup
    } catch (error) {
        throw new Error(`Error fetching tribe groups: ${error.message}`, { cause: error.cause })
    }
}

export type GetMembershipsOptions = {
    status?: string
    /** Only the caller's membership (for tribe landing tiles). */
    mine?: boolean
    /** Live asset/skill checks per committed character (members management page). */
    include_requirements?: boolean
}

export async function get_memberships(
    access_token: string,
    tribe_id: number,
    group_id: number,
    statusOrOptions?: string | GetMembershipsOptions,
): Promise<TribeMembership[]> {
    const options: GetMembershipsOptions =
        typeof statusOrOptions === 'string'
            ? { status: statusOrOptions }
            : (statusOrOptions ?? {})

    const params = new URLSearchParams()
    if (options.status) params.set('status', options.status)
    if (options.mine) params.set('mine', 'true')
    if (options.include_requirements) params.set('include_requirements', 'true')

    const query = params.toString()
    const ENDPOINT = `${API_ENDPOINT}/${tribe_id}/groups/${group_id}/memberships${query ? `?${query}` : ''}`
    console.log(`Requesting: ${ENDPOINT}`)
    try {
        const response = await fetch(ENDPOINT, {
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${access_token}`,
            },
        })
        if (!response.ok)
            throw new Error(get_error_message(response.status, `GET ${ENDPOINT}`), {
                cause: response.status
            })
        return await response.json() as TribeMembership[]
    } catch (error) {
        throw new Error(`Error fetching memberships: ${error.message}`, { cause: error.cause })
    }
}

export async function get_membership_characters_available(
    access_token: string,
    tribe_id: number,
    group_id: number,
): Promise<TribeAvailableCharacter[]> {
    const ENDPOINT = `${API_ENDPOINT}/${tribe_id}/groups/${group_id}/memberships/characters-available`
    console.log(`Requesting: ${ENDPOINT}`)
    try {
        const response = await fetch(ENDPOINT, {
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${access_token}`,
            },
        })
        if (!response.ok)
            throw new Error(get_error_message(response.status, `GET ${ENDPOINT}`), {
                cause: response.status
            })
        return await response.json() as TribeAvailableCharacter[]
    } catch (error) {
        throw new Error(`Error fetching available characters: ${error.message}`, { cause: error.cause })
    }
}

export async function refresh_available_character(
    access_token: string,
    tribe_id: number,
    group_id: number,
    character_id: number,
): Promise<TribeAvailableCharacter> {
    const ENDPOINT = `${API_ENDPOINT}/${tribe_id}/groups/${group_id}/memberships/characters-available/refresh`
    const response = await fetch(ENDPOINT, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${access_token}`,
        },
        body: JSON.stringify({ character_id }),
    })
    if (!response.ok)
        throw new Error(get_error_message(response.status, `POST ${ENDPOINT}`), {
                cause: response.status
            })
    return await response.json() as TribeAvailableCharacter
}

export async function apply_to_group(
    access_token: string,
    tribe_id: number,
    group_id: number,
    character_ids: number[] = [],
): Promise<TribeMembership> {
    const ENDPOINT = `${API_ENDPOINT}/${tribe_id}/groups/${group_id}/memberships`
    console.log(`Requesting POST: ${ENDPOINT}`)
    try {
        const response = await fetch(ENDPOINT, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${access_token}`,
            },
            body: JSON.stringify({ character_ids }),
        })
        if (!response.ok)
            throw new Error(get_error_message(response.status, `POST ${ENDPOINT}`), {
                cause: response.status
            })
        return await response.json() as TribeMembership
    } catch (error) {
        throw new Error(`Error applying to group: ${error.message}`, { cause: error.cause })
    }
}

export async function leave_group(
    access_token: string,
    tribe_id: number,
    group_id: number,
    membership_id: number,
): Promise<void> {
    const ENDPOINT = `${API_ENDPOINT}/${tribe_id}/groups/${group_id}/memberships/${membership_id}`
    console.log(`Requesting DELETE: ${ENDPOINT}`)
    try {
        const response = await fetch(ENDPOINT, {
            method: 'DELETE',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${access_token}`,
            },
        })
        if (!response.ok)
            throw new Error(get_error_message(response.status, `DELETE ${ENDPOINT}`), {
                cause: response.status
            })
    } catch (error) {
        throw new Error(`Error leaving group: ${error.message}`, { cause: error.cause })
    }
}

export async function delete_membership(
    access_token: string,
    tribe_id: number,
    group_id: number,
    membership_id: number,
): Promise<void> {
    const ENDPOINT = `${API_ENDPOINT}/${tribe_id}/groups/${group_id}/memberships/${membership_id}`
    console.log(`Requesting DELETE: ${ENDPOINT}`)
    try {
        const response = await fetch(ENDPOINT, {
            method: 'DELETE',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${access_token}`,
            },
        })
        if (!response.ok)
            throw new Error(get_error_message(response.status, `DELETE ${ENDPOINT}`), {
                cause: response.status
            })
    } catch (error) {
        throw new Error(`Error deleting membership: ${error.message}`, { cause: error.cause })
    }
}

export async function delete_membership_character(
    access_token: string,
    tribe_id: number,
    group_id: number,
    membership_id: number,
    character_id: number,
): Promise<void> {
    const ENDPOINT = `${API_ENDPOINT}/${tribe_id}/groups/${group_id}/memberships/${membership_id}/characters/${character_id}`
    console.log(`Requesting DELETE: ${ENDPOINT}`)
    try {
        const response = await fetch(ENDPOINT, {
            method: 'DELETE',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${access_token}`,
            },
        })
        if (!response.ok)
            throw new Error(get_error_message(response.status, `DELETE ${ENDPOINT}`), {
                cause: response.status
            })
    } catch (error) {
        throw new Error(`Error deleting membership character: ${error.message}`, { cause: error.cause })
    }
}

export async function approve_membership(
    access_token: string,
    tribe_id: number,
    group_id: number,
    membership_id: number,
): Promise<TribeMembership> {
    const ENDPOINT = `${API_ENDPOINT}/${tribe_id}/groups/${group_id}/memberships/${membership_id}/approve`
    console.log(`Requesting POST: ${ENDPOINT}`)
    try {
        const response = await fetch(ENDPOINT, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${access_token}`,
            },
        })
        if (!response.ok)
            throw new Error(get_error_message(response.status, `POST ${ENDPOINT}`), {
                cause: response.status
            })
        return await response.json() as TribeMembership
    } catch (error) {
        throw new Error(`Error approving membership: ${error.message}`, { cause: error.cause })
    }
}

export async function deny_membership(
    access_token: string,
    tribe_id: number,
    group_id: number,
    membership_id: number,
): Promise<TribeMembership> {
    const ENDPOINT = `${API_ENDPOINT}/${tribe_id}/groups/${group_id}/memberships/${membership_id}/deny`
    console.log(`Requesting POST: ${ENDPOINT}`)
    try {
        const response = await fetch(ENDPOINT, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${access_token}`,
            },
        })
        if (!response.ok)
            throw new Error(get_error_message(response.status, `POST ${ENDPOINT}`), {
                cause: response.status
            })
        return await response.json() as TribeMembership
    } catch (error) {
        throw new Error(`Error denying membership: ${error.message}`, { cause: error.cause })
    }
}

export async function get_tribe_group_roster(
    access_token: string,
    tribe_id: number,
    group_id: number,
): Promise<TribeGroupRosterEntry[]> {
    const ENDPOINT = `${API_ENDPOINT}/${tribe_id}/groups/${group_id}/roster`
    console.log(`Requesting: ${ENDPOINT}`)
    try {
        const response = await fetch(ENDPOINT, {
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${access_token}`,
            },
        })
        if (!response.ok)
            throw new Error(get_error_message(response.status, `GET ${ENDPOINT}`), {
                cause: response.status
            })
        return await response.json() as TribeGroupRosterEntry[]
    } catch (error) {
        throw new Error(`Error fetching tribe group roster: ${error.message}`, { cause: error.cause })
    }
}

export async function get_tribe_group_growth(
    tribe_id: number,
    group_id: number,
): Promise<TribeGroupGrowth> {
    const ENDPOINT = `${API_ENDPOINT}/${tribe_id}/groups/${group_id}/growth`
    console.log(`Requesting: ${ENDPOINT}`)
    try {
        const response = await fetch(ENDPOINT, {
            headers: { 'Content-Type': 'application/json' },
        })
        if (!response.ok)
            throw new Error(get_error_message(response.status, `GET ${ENDPOINT}`), {
                cause: response.status
            })
        return await response.json() as TribeGroupGrowth
    } catch (error) {
        throw new Error(`Error fetching tribe group growth: ${error.message}`, { cause: error.cause })
    }
}

export async function get_tribe_group_showcase(
    tribe_id: number,
    group_id: number,
    access_token?: string | false | null,
): Promise<TribeGroupShowcase> {
    const ENDPOINT = `${API_ENDPOINT}/${tribe_id}/groups/${group_id}/showcase`
    console.log(`Requesting: ${ENDPOINT}`)
    try {
        const headers: Record<string, string> = {
            'Content-Type': 'application/json',
        }
        if (access_token)
            headers['Authorization'] = `Bearer ${access_token}`

        const response = await fetch(ENDPOINT, { headers })
        if (!response.ok)
            throw new Error(get_error_message(response.status, `GET ${ENDPOINT}`), {
                cause: response.status
            })
        return await response.json() as TribeGroupShowcase
    } catch (error) {
        throw new Error(`Error fetching tribe group showcase: ${error.message}`, { cause: error.cause })
    }
}

export async function add_character_to_membership(
    access_token: string,
    tribe_id: number,
    group_id: number,
    membership_id: number,
    character_id: number,
): Promise<CharacterMembership> {
    const ENDPOINT = `${API_ENDPOINT}/${tribe_id}/groups/${group_id}/memberships/${membership_id}/characters`
    console.log(`Requesting POST: ${ENDPOINT}`)
    try {
        const response = await fetch(ENDPOINT, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${access_token}`,
            },
            body: JSON.stringify({ character_id: character_id }),
        })
        if (!response.ok)
            throw new Error(get_error_message(response.status, `POST ${ENDPOINT}`), {
                cause: response.status
            })
        return await response.json() as CharacterMembership
    } catch (error) {
        throw new Error(`Error applying to group: ${error.message}`, { cause: error.cause })
    }
}