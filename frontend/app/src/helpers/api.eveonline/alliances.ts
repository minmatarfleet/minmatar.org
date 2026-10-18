import type { AllianceEvE } from '@dtypes/api.eveonline'
import { esi_request } from '@helpers/api.eveonline/client'

const ONE_HOUR_MS = 60 * 60 * 1000

export async function get_alliance_by_id(id:number) {
    return await esi_request<AllianceEvE>(`/alliances/${id}`, {
        error: 'Error fetching alliance',
        cache_ms: ONE_HOUR_MS,
    })
}
