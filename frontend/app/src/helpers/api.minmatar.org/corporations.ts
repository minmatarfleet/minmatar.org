import type { Corporation, CorporationType, CorporationInfo, CorporationMemberDetails, CorporationOpenApplication, CorporationProjects } from '@dtypes/api.minmatar.org'
import { api_request, api_response } from '@helpers/api.minmatar.org/client'

const API_ENDPOINT =  `${import.meta.env.API_URL}/api/eveonline/corporations`

export async function get_all_corporations(corporation_type:CorporationType) {
    return await api_request<Corporation[]>(`${API_ENDPOINT}/corporations?corporation_type=${corporation_type}`, {
        error: 'Error fetching corporations',
    })
}

export async function get_corporation_by_id(access_token:string, id:number) {
    return await api_request<Corporation>(`${API_ENDPOINT}/corporations/${id}`, {
        token: access_token,
        error: 'Error fetching corporation',
    })
}

export async function get_corporation_info(id:number) {
    return await api_request<CorporationInfo>(`${API_ENDPOINT}/corporations/${id}/info`, {
        error: 'Error fetching corporation',
    })
}

export async function get_corporation_members(access_token: string, id: number) {
    const endpoint = `${API_ENDPOINT}/corporations/${id}/members`
    return await api_request<CorporationMemberDetails[] | null>(endpoint, {
        token: access_token,
        allow: [403, 404],
    })
}

export async function get_corporation_id_by_slug(slug: string) {
    return await api_request<{ corporation_id: number, slug: string } | null>(`${API_ENDPOINT}/corporations/by-slug/${encodeURIComponent(slug)}`, {
        allow: [404],
    })
}

export async function get_corporation_member_access(access_token: string, id: number) {
    const endpoint = `${API_ENDPOINT}/corporations/${id}/members/access`
    return await api_request<{
        can_view_members: boolean,
        can_view_characters: boolean,
        can_edit_settings?: boolean,
        can_view_projects?: boolean,
        can_manage_projects?: boolean,
    } | null>(endpoint, {
        token: access_token,
        allow: [403, 404],
    })
}

export async function get_corporation_open_applications(access_token: string, id: number) {
    const endpoint = `${API_ENDPOINT}/corporations/${id}/applications/open`
    return await api_request<CorporationOpenApplication[] | null>(endpoint, {
        token: access_token,
        allow: [403, 404],
    })
}
export async function get_corporation_projects(access_token: string, id: number) {
    const endpoint = `${API_ENDPOINT}/corporations/${id}/projects`
    return await api_request<CorporationProjects | null>(endpoint, {
        token: access_token,
        allow: [403, 404],
    })
}

/** Queue a sync from ESI. Resolves to the API status: 202 queued, 409 no token, 429 already pending. */
export async function refresh_corporation_projects(access_token: string, id: number) {
    const endpoint = `${API_ENDPOINT}/corporations/${id}/projects/refresh`
    const response = await api_response(endpoint, {
        method: 'POST',
        token: access_token,
        allow: [409, 429],
    })
    if (![202, 409, 429].includes(response.status)) {
        throw new Error(`HTTP error! Status — ${response.status}`, {
            cause: response.status,
        })
    }
    return response.status
}
