import type { UserGates } from '@dtypes/api.minmatar.org'
import { api_request } from '@helpers/api.minmatar.org/client'

const API_ENDPOINT = `${import.meta.env.API_URL}/api/users/me/gates`

export async function get_user_gates(access_token:string) {
    return await api_request<UserGates>(API_ENDPOINT, {
        token: access_token,
        error: 'Error fetching user gates',
    })
}
