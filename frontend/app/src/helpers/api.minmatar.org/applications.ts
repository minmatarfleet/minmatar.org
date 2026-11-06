import type {
    ApplicationRequirements,
    CorporationApplication,
    CorporationApplicationDetails,
    CorporationRequirements,
    ManagedCorporationRequirements,
    MyCorporationRequirements,
    OpenCorporationApplication,
    RequirementCreateRequest,
    RequirementRule,
    RequirementUpdateRequest,
} from '@dtypes/api.minmatar.org'
import { api_request, api_response } from '@helpers/api.minmatar.org/client'

const API_ENDPOINT =  `${import.meta.env.API_URL}/api/applications/corporations`

export async function get_corporation_applications(access_token:string, corporation_id:number) {
    return await api_request<CorporationApplication[]>(`${API_ENDPOINT}/${corporation_id}/applications`, {
        token: access_token,
        error: 'Error fetching corporation applications',
    })
}

export async function create_corporation_application(access_token:string, corporation_id:number, description:string) {
    try {
        return await api_request<CorporationApplication>(`${API_ENDPOINT}/${corporation_id}/applications`, {
            method: 'POST',
            token: access_token,
            body: {
                'description': description,
            },
        })
    } catch (error) {
        if (error instanceof Error && typeof error.cause === 'number')
            throw error
        const message = error instanceof Error ? error.message : String(error)
        throw new Error(`Error creating corporation application: ${message}`);
    }
}

export async function get_my_open_application(access_token: string) {
    return await api_request<OpenCorporationApplication>(`${import.meta.env.API_URL}/api/applications/me/open`, {
        token: access_token,
        error: 'Error fetching open corporation application',
    })
}

export async function get_corporation_applications_by_id(access_token:string, corporation_id:number, application_id) {
    return await api_request<CorporationApplicationDetails>(`${API_ENDPOINT}/${corporation_id}/applications/${application_id}`, {
        token: access_token,
        error: 'Error fetching corporation application',
    })
}

export async function accept_corporation_applications(access_token:string, corporation_id:number, application_id) {
    return await api_request<CorporationApplication[]>(`${API_ENDPOINT}/${corporation_id}/applications/${application_id}/accept`, {
        method: 'POST',
        token: access_token,
        error: 'Error accepting corporation application',
    })
}

export async function reject_corporation_applications(access_token:string, corporation_id:number, application_id) {
    return await api_request<CorporationApplication[]>(`${API_ENDPOINT}/${corporation_id}/applications/${application_id}/reject`, {
        method: 'POST',
        token: access_token,
        error: 'Error rejecting corporation application',
    })
}

export async function transfer_corporation_application(
    access_token: string,
    corporation_id: number,
    application_id: number,
    target_corporation_id: number,
) {
    return await api_request<CorporationApplication>(`${API_ENDPOINT}/${corporation_id}/applications/${application_id}/transfer`, {
        method: 'POST',
        token: access_token,
        body: {
            corporation_id: target_corporation_id,
        },
        error: 'Error transferring corporation application',
    })
}

/** Thrown for a 400 from the requirements editor: `message` is the API's reason, shown as is. */
export class RequirementError extends Error {}

async function requirement_write<T>(access_token: string, endpoint: string, method: string, body?: unknown) {
    const response = await api_response(endpoint, {
        method,
        token: access_token,
        body,
        allow: [400, 403, 404],
    })
    if (response.status === 400) {
        const detail = await response.json().catch(() => ({}))
        throw new RequirementError(detail.detail ?? 'invalid')
    }
    if (!response.ok)
        throw new RequirementError('not_allowed')
    if (response.status === 204)
        return null
    return await response.json() as T
}

/** The corp's rules and interview topics, as anyone sees them. */
export async function get_corporation_requirements(corporation_id: number) {
    return await api_request<CorporationRequirements>(`${API_ENDPOINT}/${corporation_id}/requirements`, {
        error: 'Error fetching corporation requirements',
    })
}

/** The caller's characters checked against the corp's rules. */
export async function get_my_corporation_requirements(access_token: string, corporation_id: number) {
    return await api_request<MyCorporationRequirements>(`${API_ENDPOINT}/${corporation_id}/requirements/me`, {
        token: access_token,
        error: 'Error checking corporation requirements',
    })
}

/** Rules with member pass rates, or null when the user can't edit the corp's settings. */
export async function get_managed_corporation_requirements(access_token: string, corporation_id: number) {
    return await api_request<ManagedCorporationRequirements>(`${API_ENDPOINT}/${corporation_id}/requirements/manage`, {
        token: access_token,
        allow: [403, 404],
        error: 'Error fetching corporation requirements',
    })
}

export async function create_corporation_requirement(access_token: string, corporation_id: number, rule: RequirementCreateRequest) {
    return await requirement_write<RequirementRule>(access_token, `${API_ENDPOINT}/${corporation_id}/requirements`, 'POST', rule)
}

export async function update_corporation_requirement(access_token: string, corporation_id: number, requirement_id: number, changes: RequirementUpdateRequest) {
    return await requirement_write<RequirementRule>(access_token, `${API_ENDPOINT}/${corporation_id}/requirements/${requirement_id}`, 'PATCH', changes)
}

export async function delete_corporation_requirement(access_token: string, corporation_id: number, requirement_id: number) {
    await requirement_write<null>(access_token, `${API_ENDPOINT}/${corporation_id}/requirements/${requirement_id}`, 'DELETE')
}

export async function put_corporation_interview_topics(access_token: string, corporation_id: number, topics: string[]) {
    return await requirement_write<{ interview_topics: string[] }>(access_token, `${API_ENDPOINT}/${corporation_id}/interview-topics`, 'PUT', { topics })
}

/** How an application's applicant meets the corp's rules (applicant or recruiters). */
export async function get_application_requirements(access_token: string, corporation_id: number, application_id: number) {
    return await api_request<ApplicationRequirements>(`${API_ENDPOINT}/${corporation_id}/applications/${application_id}/requirements`, {
        token: access_token,
        allow: [403, 404],
        error: 'Error fetching application requirements',
    })
}
