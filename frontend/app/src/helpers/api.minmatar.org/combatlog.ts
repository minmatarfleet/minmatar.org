import type { CombatLog, SavedCombatLog, SavedLogsRequest, CombatLogStoreOptions } from '@dtypes/api.minmatar.org'
import { query_string } from '@helpers/string'
import { api_request, api_status_is } from '@helpers/api.minmatar.org/client'

const API_ENDPOINT =  `${import.meta.env.API_URL}/api/combatlog`

export async function get_saved_logs(access_token:string, saved_logs_request:SavedLogsRequest) {
    const { user_id, fleet_id, fitting_id } = saved_logs_request

    const query_params = {
        ...(user_id && { user_id }),
        ...(fleet_id && { fleet_id }),
        ...(fitting_id && { fitting_id }),
    };

    const query = query_string(query_params)

    const ENDPOINT = `${API_ENDPOINT}${query ? `?${query}` : '/'}`

    return await api_request<SavedCombatLog[]>(ENDPOINT, {
        token: access_token,
        content_type: 'text/plain',
        error: 'Error analizing log',
    })
}

export async function get_log_by_id(access_token:string, log_id:number) {
    return await api_request<CombatLog>(`${API_ENDPOINT}/${log_id}`, {
        token: access_token,
        content_type: 'text/plain',
        error: 'Error fetching log',
    })
}

export async function analize_log(combatlog:string | Uint8Array, gzipped:boolean = false, store_options?:CombatLogStoreOptions) {
    let query = ''
    let token:string | undefined = undefined

    if (store_options) {
        const {
            access_token,
            fitting_id,
            fleet_id,
        } = store_options

        token = access_token

        const optional_attributes = {
            ...((fitting_id !== undefined && fitting_id > 0) && { "fitting_id": fitting_id }),
            ...((fleet_id !== undefined && fleet_id > 0) && { "fleet_id": fleet_id }),
            store: true,
        }

        query = query_string(optional_attributes)
    }

    const ENDPOINT = `${API_ENDPOINT}${query ? `?${query}` : query}`

    const body = combatlog instanceof Uint8Array ? new Blob([new Uint8Array(combatlog)]) : combatlog

    return await api_request<CombatLog>(ENDPOINT, {
        method: 'POST',
        token: token,
        raw_body: body,
        content_type: gzipped ? 'application/gzip' : 'text/plain',
        error: 'Error analizing log',
    })
}

export async function delete_log(access_token:string, log_id:number) {
    return await api_status_is(`${API_ENDPOINT}/${log_id}`, {
        method: 'DELETE',
        token: access_token,
        error: 'Error deleting combat log',
    })
}
