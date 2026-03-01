import type { Tribe, TribeGroup, TribeMembership, TribeGroupOutputSummary, TribeLeaderboardEntry } from '@dtypes/api.minmatar.org'
import { get_error_message } from '@helpers/string'

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

export async function get_tribe_output(tribe_id: number): Promise<TribeGroupOutputSummary[]> {
    const ENDPOINT = `${API_ENDPOINT}/${tribe_id}/output`
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

export async function get_group_leaderboard(
    tribe_id: number,
    group_id: number,
    activity_type?: string,
): Promise<TribeLeaderboardEntry[]> {
    let ENDPOINT = `${API_ENDPOINT}/${tribe_id}/groups/${group_id}/leaderboard`
    if (activity_type) ENDPOINT += `?activity_type=${encodeURIComponent(activity_type)}`
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
