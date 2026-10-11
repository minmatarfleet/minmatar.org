import type { Corporation, CorporationType, CorporationInfo, CorporationMemberDetails, CorporationMembersTop, CorporationAdmin, CorporationOpenApplication } from '@dtypes/api.minmatar.org'
import { get_error_message } from '@helpers/string'

const API_ENDPOINT =  `${import.meta.env.API_URL}/api/eveonline/corporations`

export async function get_all_corporations(corporation_type:CorporationType) {
    const headers = {
        'Content-Type': 'application/json'
    }

    const ENDPOINT = `${API_ENDPOINT}/corporations?corporation_type=${corporation_type}`

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

        return await response.json() as Corporation[];
    } catch (error) {
        throw new Error(`Error fetching corporations: ${error.message}`, { cause: error.cause });
    }
}

export async function get_corporation_by_id(access_token:string, id:number) {
    const headers = {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${access_token}`
    }

    const ENDPOINT = `${API_ENDPOINT}/corporations/${id}`

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

        return await response.json() as Corporation;
    } catch (error) {
        throw new Error(`Error fetching corporation: ${error.message}`, { cause: error.cause });
    }
}

export async function get_corporation_info(id:number) {
    const headers = {
        'Content-Type': 'application/json',
    }

    const ENDPOINT = `${API_ENDPOINT}/corporations/${id}/info`

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

        return await response.json() as CorporationInfo;
    } catch (error) {
        throw new Error(`Error fetching corporation: ${error.message}`);
    }
}

async function authorized_get<T>(access_token: string, endpoint: string): Promise<T | null> {
    const response = await fetch(endpoint, {
        headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${access_token}`,
        },
    })
    if (response.status === 403 || response.status === 404) {
        return null
    }
    if (!response.ok) {
        throw new Error(get_error_message(response.status, `GET ${endpoint}`), {
            cause: response.status,
        })
    }
    return await response.json() as T
}

export async function get_corporation_members(access_token: string, id: number) {
    const endpoint = `${API_ENDPOINT}/corporations/${id}/members`
    return await authorized_get<CorporationMemberDetails[]>(access_token, endpoint)
}

export async function get_corporation_members_top(access_token: string, id: number, metric: string) {
    const endpoint = `${API_ENDPOINT}/corporations/${id}/members/top?metric=${encodeURIComponent(metric)}`
    return await authorized_get<CorporationMembersTop>(access_token, endpoint)
}

export async function get_corporation_admin(access_token: string, id: number) {
    const endpoint = `${API_ENDPOINT}/corporations/${id}/admin`
    return await authorized_get<CorporationAdmin>(access_token, endpoint)
}

export async function get_corporation_id_by_slug(slug: string) {
    const response = await fetch(`${API_ENDPOINT}/corporations/by-slug/${encodeURIComponent(slug)}`)
    if (response.status === 404)
        return null
    if (!response.ok) {
        throw new Error(get_error_message(response.status, `GET corporations/by-slug/${slug}`), {
            cause: response.status,
        })
    }
    return await response.json() as { corporation_id: number, slug: string }
}

export async function get_corporation_member_access(access_token: string, id: number) {
    const endpoint = `${API_ENDPOINT}/corporations/${id}/members/access`
    return await authorized_get<{ can_view_members: boolean, can_view_characters: boolean }>(access_token, endpoint)
}

export async function get_corporation_open_applications(access_token: string, id: number) {
    const endpoint = `${API_ENDPOINT}/corporations/${id}/applications/open`
    return await authorized_get<CorporationOpenApplication[]>(access_token, endpoint)
}