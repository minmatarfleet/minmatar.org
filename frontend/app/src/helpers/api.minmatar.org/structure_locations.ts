import type {
    StructureLocationList,
    StructureLocationDetail,
    StructureLocationPatch,
    StructureLocationParse,
    StructureLocationDocked,
    StructureLocationSubmissionRequest,
    StructureLocationSubmission,
    StructureLocationManage,
    StructureLocationRetired,
    StructureLocationHoldings,
    StructureLocationUsers,
} from '@dtypes/api.minmatar.org'
import { api_request } from '@helpers/api.minmatar.org/client'

const API_ENDPOINT = `${import.meta.env.API_URL}/api/structures/locations`

export async function get_structure_locations(access_token:string | false | null) {
    return await api_request<StructureLocationList>(API_ENDPOINT, {
        token: access_token || undefined,
        error: 'Error fetching structures',
    })
}

export async function get_structure_location(access_token:string | false | null, location_id:number) {
    return await api_request<StructureLocationDetail>(`${API_ENDPOINT}/${location_id}`, {
        token: access_token || undefined,
        error: 'Error fetching this structure',
    })
}

export async function patch_structure_location(access_token:string, location_id:number, changes:StructureLocationPatch) {
    return await api_request<StructureLocationDetail>(`${API_ENDPOINT}/${location_id}`, {
        method: 'PATCH',
        token: access_token,
        body: changes,
    })
}

export async function post_structure_fitting(access_token:string, location_id:number, text:string) {
    return await api_request<StructureLocationDetail>(`${API_ENDPOINT}/${location_id}/fitting`, {
        method: 'POST',
        token: access_token,
        body: { text },
    })
}

export async function parse_structure_paste(access_token:string, text:string) {
    return await api_request<StructureLocationParse>(`${API_ENDPOINT}/parse`, {
        method: 'POST',
        token: access_token,
        body: { text },
    })
}

export async function get_docked_characters(access_token:string) {
    return await api_request<StructureLocationDocked[]>(`${API_ENDPOINT}/docked/characters`, {
        token: access_token,
    })
}

export async function submit_structure(access_token:string, submission:StructureLocationSubmissionRequest) {
    return await api_request<StructureLocationSubmission>(`${API_ENDPOINT}/submissions`, {
        method: 'POST',
        token: access_token,
        body: submission,
    })
}

export async function get_structure_manage(access_token:string) {
    return await api_request<StructureLocationManage>(`${API_ENDPOINT}/manage/overview`, {
        token: access_token,
        error: 'Error fetching the structure list',
    })
}

export async function approve_structure(access_token:string, submission_id:number) {
    return await api_request<StructureLocationDetail>(`${API_ENDPOINT}/submissions/${submission_id}/approve`, {
        method: 'POST',
        token: access_token,
    })
}

export async function decline_structure(access_token:string, submission_id:number, reason:string = '') {
    return await api_request<StructureLocationSubmission>(`${API_ENDPOINT}/submissions/${submission_id}/decline`, {
        method: 'POST',
        token: access_token,
        body: { reason },
    })
}

export async function retire_structure(access_token:string, location_id:number, reason:string = '') {
    return await api_request<StructureLocationRetired>(`${API_ENDPOINT}/${location_id}/retire`, {
        method: 'POST',
        token: access_token,
        body: { reason },
    })
}

export async function get_structure_holdings(access_token:string, location_id:number) {
    return await api_request<StructureLocationHoldings>(`${API_ENDPOINT}/${location_id}/holdings`, {
        token: access_token,
        error: 'Error fetching alliance holdings',
    })
}

export async function get_structure_users(access_token:string | false | null, location_id:number) {
    return await api_request<StructureLocationUsers>(`${API_ENDPOINT}/${location_id}/users`, {
        token: access_token || undefined,
        error: 'Error fetching who uses this structure',
    })
}
