import type { ManageEntityMatch, ManageSummary } from '@dtypes/api.minmatar.org'
import { api_request } from '@helpers/api.minmatar.org/client'

const API_ENDPOINT = `${import.meta.env.API_URL}/api/manage`

/** The kinds the entity search (and EntityPicker) knows. */
export const MANAGE_ENTITY_KINDS = [
    'system',
    'corporation',
    'alliance',
    'type',
    'ship',
    'location',
    'character',
    'discord_channel',
] as const

export type ManageEntityKind = typeof MANAGE_ENTITY_KINDS[number]

export function is_manage_entity_kind(kind:string | null | undefined): kind is ManageEntityKind {
    return MANAGE_ENTITY_KINDS.includes(kind as ManageEntityKind)
}

/** The manage screens the user can reach and the queues waiting on them. */
export async function get_manage_summary(access_token:string) {
    return await api_request<ManageSummary>(`${API_ENDPOINT}/summary`, {
        token: access_token,
        error: 'Error fetching the manage summary',
    })
}

/** Name search for an entity picker: id (a string), name, detail, icon_url. */
export async function search_manage_entities(access_token:string, kind:ManageEntityKind, query:string) {
    const params = new URLSearchParams({ kind, q: query })
    return await api_request<ManageEntityMatch[]>(`${API_ENDPOINT}/search?${params}`, {
        token: access_token,
        error: 'Error searching',
    }) ?? []
}
