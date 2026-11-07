import type {
    FreightManageRoute,
    FreightManageRoutes,
    FreightRouteCreate,
    FreightRoutePatch,
} from '@dtypes/api.minmatar.org'
import { api_request } from '@helpers/api.minmatar.org/client'
import type { FreightPricingInput, FreightRouteQuote } from '@helpers/market_settings'

const API_ENDPOINT = `${import.meta.env.API_URL}/api/freight/manage/routes`

/** Every route, retired ones included, or null when the user may not edit them. */
export async function get_freight_manage_routes(access_token: string) {
    return await api_request<FreightManageRoutes>(API_ENDPOINT, { token: access_token, allow: [403] })
}

export async function add_freight_route(access_token: string, payload: FreightRouteCreate) {
    return await api_request<FreightManageRoute>(API_ENDPOINT, {
        method: 'POST',
        token: access_token,
        body: payload,
    })
}

export async function patch_freight_route(access_token: string, route_id: number, payload: FreightRoutePatch) {
    return await api_request<FreightManageRoute>(`${API_ENDPOINT}/${route_id}`, {
        method: 'PATCH',
        token: access_token,
        body: payload,
    })
}

/** What the sample haul costs with these (unsaved) pricing values, and whether the XL fee is dead. */
export async function quote_freight_route(access_token: string, payload: FreightPricingInput) {
    return await api_request<FreightRouteQuote>(`${API_ENDPOINT}/quote`, {
        method: 'POST',
        token: access_token,
        body: payload,
    })
}
