import type {
    Tribe,
    TribeGroup,
    TribeMembership,
    TribeAvailableCharacter,
    TribeGroupOutputSummary,
    TribeLeaderboardEntry,
    TribeActivity,
    ActivityType,
    LogActivityPayload,
} from '@dtypes/api.minmatar.org'
import { activity_types }  from '@dtypes/api.minmatar.org'
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
            throw new Error(get_error_message(response.status, `GET ${ENDPOINT}`))
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
            throw new Error(get_error_message(response.status, `GET ${ENDPOINT}`))
        return await response.json() as Tribe[]
    } catch (error) {
        throw new Error(`Error fetching current tribes: ${error.message}`)
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
            throw new Error(get_error_message(response.status, `GET ${ENDPOINT}`))
        return await response.json() as Tribe
    } catch (error) {
        throw new Error(`Error fetching tribe: ${error.message}`)
    }
}

export async function get_tribe_groups(tribe_id: number): Promise<TribeGroup[]> {
    const ENDPOINT = `${API_ENDPOINT}/${tribe_id}/groups`
    console.log(`Requesting: ${ENDPOINT}`)
    try {
        const response = await fetch(ENDPOINT, {
            headers: { 'Content-Type': 'application/json' },
        })
        if (!response.ok)
            throw new Error(get_error_message(response.status, `GET ${ENDPOINT}`))
        return await response.json() as TribeGroup[]
    } catch (error) {
        throw new Error(`Error fetching tribe groups: ${error.message}`)
    }
}

export async function get_tribe_group(tribe_id: number, group_id:number): Promise<TribeGroup> {
    const ENDPOINT = `${API_ENDPOINT}/${tribe_id}/groups/${group_id}`
    console.log(`Requesting: ${ENDPOINT}`)
    try {
        const response = await fetch(ENDPOINT, {
            headers: { 'Content-Type': 'application/json' },
        })
        if (!response.ok)
            throw new Error(get_error_message(response.status, `GET ${ENDPOINT}`))
        return await response.json() as TribeGroup
    } catch (error) {
        throw new Error(`Error fetching tribe groups: ${error.message}`)
    }
}

export async function get_memberships(
    access_token: string,
    tribe_id: number,
    group_id: number,
    status?: string,
): Promise<TribeMembership[]> {
    let ENDPOINT = `${API_ENDPOINT}/${tribe_id}/groups/${group_id}/memberships`
    if (status) ENDPOINT += `?status=${status}`
    console.log(`Requesting: ${ENDPOINT}`)
    try {
        const response = await fetch(ENDPOINT, {
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${access_token}`,
            },
        })
        if (!response.ok)
            throw new Error(get_error_message(response.status, `GET ${ENDPOINT}`))
        return await response.json() as TribeMembership[]
    } catch (error) {
        throw new Error(`Error fetching memberships: ${error.message}`)
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
            throw new Error(get_error_message(response.status, `GET ${ENDPOINT}`))
        return await response.json() as TribeAvailableCharacter[]
    } catch (error) {
        throw new Error(`Error fetching available characters: ${error.message}`)
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
        throw new Error(get_error_message(response.status, `POST ${ENDPOINT}`))
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
            throw new Error(get_error_message(response.status, `POST ${ENDPOINT}`))
        return await response.json() as TribeMembership
    } catch (error) {
        throw new Error(`Error applying to group: ${error.message}`)
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
            throw new Error(get_error_message(response.status, `DELETE ${ENDPOINT}`))
    } catch (error) {
        throw new Error(`Error leaving group: ${error.message}`)
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
            throw new Error(get_error_message(response.status, `DELETE ${ENDPOINT}`))
    } catch (error) {
        throw new Error(`Error deleting membership: ${error.message}`)
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
            throw new Error(get_error_message(response.status, `DELETE ${ENDPOINT}`))
    } catch (error) {
        throw new Error(`Error deleting membership character: ${error.message}`)
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
            throw new Error(get_error_message(response.status, `POST ${ENDPOINT}`))
        return await response.json() as TribeMembership
    } catch (error) {
        throw new Error(`Error approving membership: ${error.message}`)
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
            throw new Error(get_error_message(response.status, `POST ${ENDPOINT}`))
        return await response.json() as TribeMembership
    } catch (error) {
        throw new Error(`Error denying membership: ${error.message}`)
    }
}

export async function log_activity(
    access_token: string,
    tribe_id: number,
    group_id: number,
    payload: Omit<LogActivityPayload, 'activity_type'> & { activity_type: string },
) {
    const headers = {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${access_token}`,
    }

    const rawType = (payload.activity_type as string).toLowerCase()

    const activity_type = activity_types.includes(rawType as ActivityType)
        ? (rawType as ActivityType)
        : 'custom'

    const body: LogActivityPayload = {
        ...payload,
        activity_type,
        description: payload.description ?? '',
    }

    const ENDPOINT = `${API_ENDPOINT}/${tribe_id}/groups/${group_id}/activities`

    console.log(`Requesting POST: ${ENDPOINT}`)
    try {
        const response = await fetch(ENDPOINT, {
            method: 'POST',
            headers,
            body: JSON.stringify(body),
        })

        if (!response.ok)
            throw new Error(get_error_message(response.status, `POST ${ENDPOINT}`))

        return await response.json() as TribeActivity
    } catch (error) {
        throw new Error(`Error logging tribe activity: ${error.message}`)
    }
}

export async function get_output(period_start?: Date, period_end?: Date) {
    const query_params = {
        ...(period_start && { period_start }),
        ...(period_end && { period_end }),
    }

    const query = query_string(query_params)

    const ENDPOINT = `${API_ENDPOINT}/output${query ? `?${query}` : ''}`

    console.log(`Requesting: ${ENDPOINT}`)
    try {
        const response = await fetch(ENDPOINT, {
            headers: { 'Content-Type': 'application/json' },
        })

        if (!response.ok)
            throw new Error(get_error_message(response.status, `GET ${ENDPOINT}`))

        return await response.json() as TribeGroupOutputSummary[]
    } catch (error) {
        throw new Error(`Error fetching tribes output: ${error.message}`)
    }
}

export async function get_tribe_output(tribe_id: number, period_start?: Date, period_end?: Date) {
    const query_params = {
        ...(period_start && { period_start }),
        ...(period_end && { period_end }),
    }

    const query = query_string(query_params)

    const ENDPOINT = `${API_ENDPOINT}/${tribe_id}/output${query ? `?${query}` : ''}`
    console.log(`Requesting: ${ENDPOINT}`)
    try {
        const response = await fetch(ENDPOINT, {
            headers: { 'Content-Type': 'application/json' },
        })

        if (!response.ok)
            throw new Error(get_error_message(response.status, `GET ${ENDPOINT}`))

        return await response.json() as TribeGroupOutputSummary[]
    } catch (error) {
        throw new Error(`Error fetching tribe output: ${error.message}`)
    }
}

export async function get_group_output(
    tribe_id: number,
    group_id: number,
    period_start?: Date,
    period_end?: Date
) {
    const query_params = {
        ...(period_start && { period_start }),
        ...(period_end && { period_end }),
    }

    const query = query_string(query_params)

    const ENDPOINT = `${API_ENDPOINT}/${tribe_id}/groups/${group_id}/output${query ? `?${query}` : ''}`

    console.log(`Requesting: ${ENDPOINT}`)
    try {
        const response = await fetch(ENDPOINT, {
            headers: { 'Content-Type': 'application/json' },
        })

        if (!response.ok)
            throw new Error(get_error_message(response.status, `GET ${ENDPOINT}`))

        return await response.json() as TribeGroupOutputSummary
    } catch (error) {
        throw new Error(`Error fetching group output: ${error.message}`)
    }
}

export async function get_group_leaderboard(
    tribe_id: number,
    group_id: number,
    activity_type?: string,
    period_start?: Date,
    period_end?: Date
) {
    const query_params = {
        ...(activity_type && { activity_type }),
        ...(period_start && { period_start }),
        ...(period_end && { period_end }),
    }

    const query = query_string(query_params)

    let ENDPOINT = `${API_ENDPOINT}/${tribe_id}/groups/${group_id}/leaderboard${query ? `?${query}` : ''}`

    console.log(`Requesting: ${ENDPOINT}`)
    try {
        const response = await fetch(ENDPOINT, {
            headers: { 'Content-Type': 'application/json' },
        })

        if (!response.ok)
            throw new Error(get_error_message(response.status, `GET ${ENDPOINT}`))

        return await response.json() as TribeLeaderboardEntry[]
    } catch (error) {
        throw new Error(`Error fetching group leaderboard: ${error.message}`)
    }
}