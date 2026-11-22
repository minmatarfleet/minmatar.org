import { api_request } from '@helpers/api.minmatar.org/client'
import type { LandingPulse, LandingWeek } from '@dtypes/api.minmatar.org'

const API_ENDPOINT = `${import.meta.env.API_URL}/api/alliance/landing`

/** Public: the new landing page needs no login. */
export async function get_landing_pulse() {
    return await api_request<LandingPulse>(`${API_ENDPOINT}/pulse`, {
        error: 'Error fetching the landing pulse',
    })
}

export async function get_landing_week(tab:string, page:number) {
    const query = new URLSearchParams({ tab, page: String(page) })
    return await api_request<LandingWeek>(`${API_ENDPOINT}/week?${query}`, {
        error: 'Error fetching the landing week',
    })
}
