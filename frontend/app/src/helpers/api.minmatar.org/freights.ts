import type { FreightRoute, RouteCost, FreightContract, SpaceTruckerStatistics, FreightContractsStats } from '@dtypes/api.minmatar.org'
import { api_request, type ApiToken } from '@helpers/api.minmatar.org/client'

const API_ENDPOINT = `${import.meta.env.API_URL}/api/freight`

export async function get_routes(token?: ApiToken) {
    return await api_request<FreightRoute[]>(`${API_ENDPOINT}/routes`, {
        token,
        error: 'Error fetching freight routes',
    })
}

export async function get_route_cost(route_id: number, m3: number, collateral: number, token?: ApiToken) {
    const params = new URLSearchParams({ m3: String(m3), collateral: String(collateral) })
    const ENDPOINT = `${API_ENDPOINT}/routes/${route_id}/cost?${params}`

    return await api_request<RouteCost>(ENDPOINT, {
        token,
        error: 'Error fetching freight route cost',
    })
}

export async function get_contracts(history:boolean = false, token?: ApiToken) {
    return await api_request<FreightContract[]>(`${API_ENDPOINT}/contracts${history ? '/history' : ''}`, {
        token,
        error: 'Error fetching freight contracts',
    })
}

export async function get_contracts_stats(token?: ApiToken) {
    return await api_request<FreightContractsStats>(`${API_ENDPOINT}/contracts/stats`, {
        token,
        error: 'Error fetching freight contracts stats',
    })
}

export async function get_characters_statistics(token?: ApiToken) {
    return await api_request<SpaceTruckerStatistics[]>(`${API_ENDPOINT}/character-statistics`, {
        token,
        error: 'Error fetching freight contracts',
    })
}

export function freight_contracts_history_csv_url(): string {
    return '/api/freight/contracts/history.csv'
}
