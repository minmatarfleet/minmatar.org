import { api_request } from '@helpers/api.minmatar.org/client'
import type { LandingPulse } from '@dtypes/api.minmatar.org'

const API_ENDPOINT = `${import.meta.env.API_URL}/api/alliance/landing`

export async function get_landing_pulse(access_token:string) {
    return await api_request<LandingPulse>(`${API_ENDPOINT}/pulse`, {
        token: access_token,
        error: 'Error fetching the landing pulse',
    })
}
