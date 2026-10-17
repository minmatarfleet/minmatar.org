import type {
    TribeAbout,
    Tribe,
    TribeGroup,
    TribeMembership,
    TribeAvailableCharacter,
    TribeGroupRosterEntry,
    TribeGroupShowcase,
    CharacterMembership,
    TribeExternalGuildJoin,
} from '@dtypes/api.minmatar.org'
import { query_string } from '@helpers/string'
import { api_request, api_response } from '@helpers/api.minmatar.org/client'

const API_ENDPOINT = `${import.meta.env.API_URL}/api/tribes`

export async function get_tribes(): Promise<Tribe[]> {
    return await api_request<Tribe[]>(API_ENDPOINT, {
        error: 'Error fetching tribes',
    })
}

export async function get_tribe(id: number): Promise<Tribe> {
    return await api_request<Tribe>(`${API_ENDPOINT}/${id}`, {
        error: 'Error fetching tribe',
    })
}

export async function get_tribe_about(
    tribe_id: number,
    access_token?: string | false | null,
): Promise<TribeAbout> {
    return await api_request<TribeAbout>(`${API_ENDPOINT}/${tribe_id}/about`, {
        token: access_token,
        error: 'Error fetching tribe about',
    })
}

export async function get_tribe_groups(
    tribe_id: number,
    access_token?: string | false | null,
): Promise<TribeGroup[]> {
    return await api_request<TribeGroup[]>(`${API_ENDPOINT}/${tribe_id}/groups`, {
        token: access_token,
        error: 'Error fetching tribe groups',
    })
}

export async function get_tribe_group(
    tribe_id: number,
    group_id: number,
    access_token?: string | false | null,
): Promise<TribeGroup> {
    return await api_request<TribeGroup>(`${API_ENDPOINT}/${tribe_id}/groups/${group_id}`, {
        token: access_token,
        error: 'Error fetching tribe groups',
    })
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

    return await api_request<TribeMembership[]>(`${API_ENDPOINT}/${tribe_id}/groups/${group_id}/memberships${query ? `?${query}` : ''}`, {
        token: access_token,
        error: 'Error fetching memberships',
    })
}

export async function get_membership_characters_available(
    access_token: string,
    tribe_id: number,
    group_id: number,
): Promise<TribeAvailableCharacter[]> {
    return await api_request<TribeAvailableCharacter[]>(`${API_ENDPOINT}/${tribe_id}/groups/${group_id}/memberships/characters-available`, {
        token: access_token,
        error: 'Error fetching available characters',
    })
}

export async function apply_to_group(
    access_token: string,
    tribe_id: number,
    group_id: number,
    character_ids: number[] = [],
): Promise<TribeMembership> {
    return await api_request<TribeMembership>(`${API_ENDPOINT}/${tribe_id}/groups/${group_id}/memberships`, {
        method: 'POST',
        token: access_token,
        body: { character_ids },
        error: 'Error applying to group',
    })
}

export async function leave_group(
    access_token: string,
    tribe_id: number,
    group_id: number,
    membership_id: number,
): Promise<void> {
    await api_response(`${API_ENDPOINT}/${tribe_id}/groups/${group_id}/memberships/${membership_id}`, {
        method: 'DELETE',
        token: access_token,
        error: 'Error leaving group',
    })
}

export async function delete_membership(
    access_token: string,
    tribe_id: number,
    group_id: number,
    membership_id: number,
): Promise<void> {
    await api_response(`${API_ENDPOINT}/${tribe_id}/groups/${group_id}/memberships/${membership_id}`, {
        method: 'DELETE',
        token: access_token,
        error: 'Error deleting membership',
    })
}

export async function delete_membership_character(
    access_token: string,
    tribe_id: number,
    group_id: number,
    membership_id: number,
    character_id: number,
): Promise<void> {
    await api_response(`${API_ENDPOINT}/${tribe_id}/groups/${group_id}/memberships/${membership_id}/characters/${character_id}`, {
        method: 'DELETE',
        token: access_token,
        error: 'Error deleting membership character',
    })
}

export async function approve_membership(
    access_token: string,
    tribe_id: number,
    group_id: number,
    membership_id: number,
): Promise<TribeMembership> {
    return await api_request<TribeMembership>(`${API_ENDPOINT}/${tribe_id}/groups/${group_id}/memberships/${membership_id}/approve`, {
        method: 'POST',
        token: access_token,
        error: 'Error approving membership',
    })
}

export async function deny_membership(
    access_token: string,
    tribe_id: number,
    group_id: number,
    membership_id: number,
): Promise<TribeMembership> {
    return await api_request<TribeMembership>(`${API_ENDPOINT}/${tribe_id}/groups/${group_id}/memberships/${membership_id}/deny`, {
        method: 'POST',
        token: access_token,
        error: 'Error denying membership',
    })
}

export async function get_tribe_group_roster(
    access_token: string,
    tribe_id: number,
    group_id: number,
): Promise<TribeGroupRosterEntry[]> {
    return await api_request<TribeGroupRosterEntry[]>(`${API_ENDPOINT}/${tribe_id}/groups/${group_id}/roster`, {
        token: access_token,
        error: 'Error fetching tribe group roster',
    })
}

export async function get_tribe_group_showcase(
    tribe_id: number,
    group_id: number,
    access_token?: string | false | null,
): Promise<TribeGroupShowcase> {
    return await api_request<TribeGroupShowcase>(`${API_ENDPOINT}/${tribe_id}/groups/${group_id}/showcase`, {
        token: access_token,
        error: 'Error fetching tribe group showcase',
    })
}

export async function add_character_to_membership(
    access_token: string,
    tribe_id: number,
    group_id: number,
    membership_id: number,
    character_id: number,
): Promise<CharacterMembership> {
    return await api_request<CharacterMembership>(`${API_ENDPOINT}/${tribe_id}/groups/${group_id}/memberships/${membership_id}/characters`, {
        method: 'POST',
        token: access_token,
        body: { character_id: character_id },
        error: 'Error applying to group',
    })
}

export async function get_external_guild_join(
    access_token: string,
    group_id: number,
    redirect_url: string,
): Promise<TribeExternalGuildJoin> {
    const query = query_string({
        group_id,
        redirect_url,
    })

    return await api_request<TribeExternalGuildJoin>(`${API_ENDPOINT}/external-guild/join?${query}`, {
        token: access_token,
        error: 'Error starting external guild join',
    })
}
