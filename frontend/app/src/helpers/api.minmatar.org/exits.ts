import type { DepartureAnswer, DepartureGroup, HistoryEntry } from '@dtypes/api.minmatar.org'
import { api_request } from '@helpers/api.minmatar.org/client'

const API_ENDPOINT = `${import.meta.env.API_URL}/api/exits`

export type DepartureState = 'open' | 'answered' | 'all'

/** The CEO's Departures tab. Null when the viewer isn't the CEO. */
export async function get_departures(access_token: string, corporation_id: number, state: DepartureState) {
    return await api_request<DepartureGroup[] | null>(
        `${API_ENDPOINT}/corporations/${corporation_id}/departures?state=${state}`,
        { token: access_token, allow: [403, 404] },
    )
}

export async function post_departure_answers(access_token: string, corporation_id: number, body: DepartureAnswer) {
    return await api_request<DepartureGroup[]>(
        `${API_ENDPOINT}/corporations/${corporation_id}/departures/answers`,
        { method: 'POST', token: access_token, body },
    )
}

export async function clear_rejoin_flag(access_token: string, flag_id: number) {
    return await api_request<{ cleared: boolean }>(
        `${API_ENDPOINT}/flags/${flag_id}/clear`,
        { method: 'POST', token: access_token },
    )
}

/** An applicant's alliance history, for the corporation's recruiters. Null for anyone else. */
export async function get_application_history(access_token: string, application_id: number) {
    return await api_request<HistoryEntry[] | null>(
        `${API_ENDPOINT}/applications/${application_id}/history`,
        { token: access_token, allow: [403, 404] },
    )
}
