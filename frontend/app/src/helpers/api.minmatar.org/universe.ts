import type {
    UniverseStructure,
    UniverseStructureList,
    UniverseStructureMatch,
    UniverseStructureReport,
    UniverseTimerList,
    UniverseMoonList,
    UniverseMoonReport,
} from '@dtypes/api.minmatar.org'
import { api_request } from '@helpers/api.minmatar.org/client'

const API_ENDPOINT = `${import.meta.env.API_URL}/api/universe`

export async function get_universe_structures(access_token:string) {
    return await api_request<UniverseStructureList>(`${API_ENDPOINT}/structures`, {
        token: access_token,
        error: 'Error fetching structures',
    })
}

export async function match_universe_structures(access_token:string, system_name:string, type_id:number, name:string) {
    return await api_request<UniverseStructureMatch>(`${API_ENDPOINT}/structures/match`, {
        method: 'POST',
        token: access_token,
        body: { system_name, type_id, name },
    })
}

export async function report_universe_structure(access_token:string, report:UniverseStructureReport) {
    return await api_request<{ status: string }>(`${API_ENDPOINT}/structures/report`, {
        method: 'POST',
        token: access_token,
        body: report,
    })
}

export async function set_universe_structure_visibility(access_token:string, structure_id:number, visibility:string) {
    return await api_request<UniverseStructure>(`${API_ENDPOINT}/structures/${structure_id}/visibility`, {
        method: 'PATCH',
        token: access_token,
        body: { visibility },
    })
}

export async function confirm_universe_structure(access_token:string, structure_id:number) {
    return await api_request<UniverseStructure>(`${API_ENDPOINT}/structures/${structure_id}/confirm`, {
        method: 'POST',
        token: access_token,
    })
}

export async function get_universe_timers(access_token:string) {
    return await api_request<UniverseTimerList>(`${API_ENDPOINT}/timers`, {
        token: access_token,
        error: 'Error fetching timers',
    })
}

export async function get_universe_moons(access_token:string, query:{ page?: number, q?: string, rarity?: number } = {}) {
    const params = new URLSearchParams()
    if (query.page && query.page > 1) params.set('page', String(query.page))
    if (query.q) params.set('q', query.q)
    if (query.rarity) params.set('rarity', String(query.rarity))
    const search = params.size > 0 ? `?${params}` : ''
    return await api_request<UniverseMoonList>(`${API_ENDPOINT}/moons${search}`, {
        token: access_token,
        error: 'Error fetching moons',
    })
}

export async function report_universe_moons(access_token:string, paste:string) {
    return await api_request<UniverseMoonReport>(`${API_ENDPOINT}/moons/report`, {
        method: 'POST',
        token: access_token,
        body: { paste },
    })
}
