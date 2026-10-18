import type { StructureTimer, StructureTimerRequest, VerifyStructureTimerRequest } from '@dtypes/api.minmatar.org'
import { api_request } from '@helpers/api.minmatar.org/client'

const API_ENDPOINT = `${import.meta.env.API_URL}/api/structures/`

export async function get_structure_timers(access_token:string, active:boolean = true) {
    return await api_request<StructureTimer[]>(`${API_ENDPOINT}timers?active=${JSON.stringify(active)}`, {
        token: access_token,
        error: 'Error fetching structure timers',
    })
}

export async function create_structure_timer(access_token:string, timer:StructureTimerRequest) {
    return await api_request<StructureTimer>(`${API_ENDPOINT}timers`, {
        method: 'POST',
        token: access_token,
        body: timer,
        error: 'Error creating structure timer',
    })
}

export async function verify_structure_timer(access_token:string, timer_id:number, request:VerifyStructureTimerRequest) {
    return await api_request<StructureTimer>(`${API_ENDPOINT}timers/${timer_id}/verify`, {
        method: 'POST',
        token: access_token,
        body: request,
        error: 'Error creating structure timer',
    })
}