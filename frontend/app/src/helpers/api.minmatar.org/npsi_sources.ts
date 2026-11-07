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

// Fields the manage redesign added to the backend schema. The generated
// NpsiSource/NpsiSourceList gain them at the next openapi regen; until then
// they are optional here, so an older backend still renders.
export type NpsiSourceRow = NpsiSource & {
    last_error_kind?:   string;
    upcoming_count?:    number;
    fc_character_id?:   number | null;
}

export type NpsiSourceListing = Omit<NpsiSourceList, 'sources'> & {
    sources:                NpsiSourceRow[];
    feed_timeout_seconds?:  number;
}

/** POST /npsi-sources/{id}/try: a dry run that stores and sends nothing. */
export type NpsiTryResult = {
    ok:                     boolean;
    error:                  string;
    error_kind:             string;
    item_count:             number;
    upcoming_count:         number;
    upcoming:               { summary: string, start_time: string, character_name: string }[];
    feed_timeout_seconds?:  number;
}

export async function get_npsi_source_listing(access_token: string) {
    return await get_npsi_sources(access_token) as NpsiSourceListing
}

export async function try_npsi_source(access_token: string, source_id: number) {
    return await api_request<NpsiTryResult>(`${API_ENDPOINT}/${source_id}/try`, {
        method: 'POST',
        token: access_token,
        error: 'Error reading the feed',
    })
}
