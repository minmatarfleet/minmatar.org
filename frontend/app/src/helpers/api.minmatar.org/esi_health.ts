import type {
    DirectorToken,
    EsiHealthCorporation,
    EsiHealthPilot,
    EsiMessageResult,
    EsiScopeRollout,
    EsiScopeRolloutPatch,
} from '@dtypes/api.minmatar.org'
import { api_request } from '@helpers/api.minmatar.org/client'

const API_ENDPOINT = `${import.meta.env.API_URL}/api/esi-health`

export const get_esi_health_corporations = (token: string) =>
    api_request<EsiHealthCorporation[]>(`${API_ENDPOINT}/corporations`, { token })

export const get_esi_health_pilots = (token: string) =>
    api_request<EsiHealthPilot[]>(`${API_ENDPOINT}/pilots`, { token })

export const get_esi_scope_rollouts = (token: string) =>
    api_request<EsiScopeRollout[]>(`${API_ENDPOINT}/scopes`, { token })

export const save_esi_scope_rollout = (token: string, id: number, body: EsiScopeRolloutPatch) =>
    api_request<EsiScopeRollout>(`${API_ENDPOINT}/scopes/${id}`, { method: 'PATCH', token, body })

/** No user ids: everyone who needs to re-add, isn't On Leave and wasn't messaged this week. */
export const send_esi_messages = (token: string, user_ids: number[] = []) =>
    api_request<EsiMessageResult>(`${API_ENDPOINT}/messages`, { method: 'POST', token, body: { user_ids } })

export const get_director_token = (token: string, corporation_id: number) =>
    api_request<DirectorToken>(`${API_ENDPOINT}/corporations/${corporation_id}/director-token`, { token })
