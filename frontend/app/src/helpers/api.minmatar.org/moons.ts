import type { SystemMoon, MoonSummarySystem } from '@dtypes/api.minmatar.org'
import { query_string } from '@helpers/string'
import { api_request } from '@helpers/api.minmatar.org/client'

const API_ENDPOINT = `${import.meta.env.API_URL}/api/moons`

export async function get_system_moons(access_token:string, system:string) {
    return await api_request<SystemMoon[]>(`${API_ENDPOINT}?${query_string({'system': system})}`, {
        token: access_token,
        error: 'Error fetching system moons',
    })
}

export async function get_moon_summary(access_token:string) {
    return await api_request<MoonSummarySystem[]>(`${API_ENDPOINT}/summary`, {
        token: access_token,
        error: 'Error fetching moon summary',
    })
}

export async function add_moon(access_token:string, paste:string) {
    return await api_request<number[]>(`${import.meta.env.API_URL}/api/moon_paste`, {
        method: 'POST',
        token: access_token,
        body: {
            paste: paste
        },
        error: 'Error adding moon',
    })
}