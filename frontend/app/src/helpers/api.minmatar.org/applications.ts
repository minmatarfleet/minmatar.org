import type {
    CorporationApplication,
    CorporationApplicationDetails,
    OpenCorporationApplication,
} from '@dtypes/api.minmatar.org'
import { api_request } from '@helpers/api.minmatar.org/client'

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
