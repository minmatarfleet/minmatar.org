import { api_request } from '@helpers/api.minmatar.org/client'
import type { TrialReport, TrialStatus } from '@dtypes/api.minmatar.org'

const API_ENDPOINT = `${import.meta.env.API_URL}/api/alliance/trial`

export async function get_my_trial(access_token:string) {
    return await api_request<TrialReport>(`${API_ENDPOINT}/me`, {
        token: access_token,
        error: 'Error fetching your trial',
    })
}

export async function get_my_trial_status(access_token:string) {
    return await api_request<TrialStatus>(`${API_ENDPOINT}/me/status`, {
        token: access_token,
        error: 'Error fetching your trial status',
    })
}
