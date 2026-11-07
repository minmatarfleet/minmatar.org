import type {
    DoctrineChangeBody,
    DoctrineChangePreview,
    DoctrineChangeRequestRow,
    FittingChangeBody,
    NewFittingBody,
    NewFittingResult,
} from '@dtypes/api.minmatar.org'
import { api_request } from '@helpers/api.minmatar.org/client'

const API_URL = import.meta.env.API_URL

export type ChangeReviewAction = 'approve' | 'reject' | 'cancel'

export async function get_change_requests(access_token:string, status:'pending' | 'all' = 'pending') {
    return await api_request<DoctrineChangeRequestRow[]>(`${API_URL}/api/change-requests/?status=${status}`, {
        token: access_token,
        error: 'Error fetching change requests',
    })
}

export async function review_change_request(
    access_token:string,
    kind:'fitting' | 'doctrine',
    request_id:number,
    action:ChangeReviewAction,
    review_note:string = '',
) {
    return await api_request<DoctrineChangeRequestRow>(`${API_URL}/api/change-requests/${kind}/${request_id}/review`, {
        method: 'POST',
        token: access_token,
        body: { action, review_note },
        error: 'Error reviewing change request',
    })
}

export async function submit_fitting_change(access_token:string, fitting_id:number, body:FittingChangeBody) {
    return await api_request<DoctrineChangePreview>(`${API_URL}/api/fittings/${fitting_id}/change-requests`, {
        method: 'POST',
        token: access_token,
        body,
        error: 'Error submitting fitting change',
    })
}

export async function submit_doctrine_change(access_token:string, doctrine_id:number, body:DoctrineChangeBody) {
    return await api_request<DoctrineChangePreview>(`${API_URL}/api/doctrines/${doctrine_id}/change-requests`, {
        method: 'POST',
        token: access_token,
        body,
        error: 'Error submitting doctrine change',
    })
}

/** Read pasted EFT (preview), or submit it as a new fitting waiting for review. */
export async function submit_new_fitting(access_token:string, body:NewFittingBody) {
    return await api_request<NewFittingResult>(`${API_URL}/api/fittings/new/change-requests`, {
        method: 'POST',
        token: access_token,
        body,
        error: 'Error reading the fitting',
    })
}
