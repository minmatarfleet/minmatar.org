import type {
    FreightManageRoute,
    FreightManageRoutes,
    FreightRouteCreate,
    FreightRoutePatch,
} from '@dtypes/api.minmatar.org'
import { api_request } from '@helpers/api.minmatar.org/client'

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
