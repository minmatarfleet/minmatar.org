import type { CorporationEvE } from '@dtypes/api.eveonline'
import { esi_request } from '@helpers/api.eveonline/client'

const ONE_HOUR_MS = 60 * 60 * 1000

export async function get_corporation_by_id(id:number) {
    return await esi_request<CorporationEvE>(`/corporations/${id}`, {
        error: 'Error fetching corporation',
        cache_ms: ONE_HOUR_MS,
    })
}
