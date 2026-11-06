import type { MarketHub, MarketHubCreate, MarketHubExpectations, MarketHubPatch } from '@dtypes/api.minmatar.org'
import { api_request } from '@helpers/api.minmatar.org/client'

const API_ENDPOINT = `${import.meta.env.API_URL}/api/market/hubs`

/** Every location with its market flags, or null when the user may not manage hubs. */
export async function get_market_hubs(access_token: string) {
    return await api_request<MarketHub[]>(API_ENDPOINT, { token: access_token, allow: [403] })
}

export async function add_market_hub(access_token: string, payload: MarketHubCreate) {
    return await api_request<MarketHub>(API_ENDPOINT, { method: 'POST', token: access_token, body: payload })
}

export async function patch_market_hub(access_token: string, location_id: number, payload: MarketHubPatch) {
    return await api_request<MarketHub>(`${API_ENDPOINT}/${location_id}`, {
        method: 'PATCH',
        token: access_token,
        body: payload,
    })
}

export async function remove_market_hub(access_token: string, location_id: number) {
    return await api_request<MarketHub>(`${API_ENDPOINT}/${location_id}`, { method: 'DELETE', token: access_token })
}

export async function get_market_hub_expectations(access_token: string, location_id: number) {
    return await api_request<MarketHubExpectations>(`${API_ENDPOINT}/${location_id}/expectations`, {
        token: access_token,
        allow: [403, 404],
    })
}

export async function set_market_expectation_tracked(
    access_token: string,
    location_id: number,
    kind: 'fittings' | 'contracts',
    fitting_id: number,
    tracked: boolean,
) {
    return await api_request(`${API_ENDPOINT}/${location_id}/expectations/${kind}/${fitting_id}`, {
        method: 'PUT',
        token: access_token,
        body: { tracked },
    })
}

export async function add_market_item_expectation(access_token: string, location_id: number, type_id: number) {
    return await api_request(`${API_ENDPOINT}/${location_id}/expectations/items`, {
        method: 'POST',
        token: access_token,
        body: { type_id },
    })
}

export async function remove_market_item_expectation(access_token: string, location_id: number, type_id: number) {
    return await api_request(`${API_ENDPOINT}/${location_id}/expectations/items/${type_id}`, {
        method: 'DELETE',
        token: access_token,
    })
}

export async function set_expectations_from_doctrine(access_token: string, location_id: number, doctrine_id: number) {
    return await api_request<{ created: number, already_tracked: number }>(
        `${API_ENDPOINT}/${location_id}/expectations/from-doctrine`,
        { method: 'POST', token: access_token, body: { doctrine_id } },
    )
}

export async function search_market_types(access_token: string, query: string) {
    return await api_request<{ type_id: number, name: string }[]>(
        `${API_ENDPOINT}-type-search?q=${encodeURIComponent(query)}`,
        { token: access_token, allow: [403] },
    )
}
