import type { StructurePing, StructureTimer, StructureTimerPatch, StructureTimerRequest, VerifyStructureTimerRequest } from '@dtypes/api.minmatar.org'
import { api_request, api_status_is } from '@helpers/api.minmatar.org/client'

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


// Corrections and the ping log answer 403 without the structures.timers.correct feature.
export async function update_structure_timer(access_token:string, timer_id:number, changes:StructureTimerPatch) {
    return await api_request<StructureTimer>(`${API_ENDPOINT}timers/${timer_id}`, {
        method: 'PATCH',
        token: access_token,
        body: changes,
    })
}

export async function delete_structure_timer(access_token:string, timer_id:number) {
    return await api_status_is(`${API_ENDPOINT}timers/${timer_id}`, {
        method: 'DELETE',
        token: access_token,
    }, 204)
}

export async function get_structure_pings(access_token:string, failed_only:boolean = false) {
    return await api_request<StructurePing[]>(`${API_ENDPOINT}pings?failed_only=${failed_only}`, {
        token: access_token,
        error: 'Error fetching structure pings',
    })
}
