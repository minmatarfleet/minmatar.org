import type { Player, PrimeTime } from '@dtypes/api.minmatar.org'
import { api_request, api_status_is } from '@helpers/api.minmatar.org/client'

const API_ENDPOINT =  `${import.meta.env.API_URL}/api/eveonline/players`

export async function get_current_player(access_token:string) {
    return await api_request<Player>(`${API_ENDPOINT}/current`, {
        token: access_token,
        error: 'Error fetching current player',
    })
}

export async function update_prime_time(access_token:string, prime_time:PrimeTime, nickname:string) {
    return await api_status_is(`${API_ENDPOINT}/current`, {
        method: 'PATCH',
        token: access_token,
        body: { nickname: nickname, prime_time: prime_time },
        error: 'Error setting prime time',
    })
}