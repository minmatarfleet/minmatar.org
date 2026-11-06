import type { NpsiEventPreview, NpsiSource, NpsiSourceCreate, NpsiSourceList, NpsiSourcePatch } from '@dtypes/api.minmatar.org'
import { api_request } from '@helpers/api.minmatar.org/client'

// External NPSI calendars imported into the fleet schedule.
// Every endpoint answers 403 without the fleets.npsi_sources.manage feature.
const API_ENDPOINT = `${import.meta.env.API_URL}/api/fleets/npsi-sources`

export async function get_npsi_sources(access_token: string) {
    return await api_request<NpsiSourceList>(API_ENDPOINT, {
        token: access_token,
        error: 'Error fetching NPSI sources',
    })
}

export async function create_npsi_source(access_token: string, source: NpsiSourceCreate) {
    return await api_request<NpsiSource>(API_ENDPOINT, {
        method: 'POST',
        token: access_token,
        body: source,
    })
}

export async function update_npsi_source(access_token: string, source_id: number, changes: NpsiSourcePatch) {
    return await api_request<NpsiSource>(`${API_ENDPOINT}/${source_id}`, {
        method: 'PATCH',
        token: access_token,
        body: changes,
    })
}

export async function get_npsi_source_events(access_token: string, source_id: number) {
    return await api_request<NpsiEventPreview[]>(`${API_ENDPOINT}/${source_id}/events`, {
        token: access_token,
        error: 'Error fetching imported events',
    })
}
