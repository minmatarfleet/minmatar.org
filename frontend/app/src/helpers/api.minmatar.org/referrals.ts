import { api_request, api_status_is } from '@helpers/api.minmatar.org/client'
import type { ReferralLinkStats } from '@dtypes/api.minmatar.org'

const API_ENDPOINT = `${import.meta.env.API_URL}/api/referrals`

export async function get_link_stats(access_token:string) {
    return await api_request<ReferralLinkStats[]>(`${API_ENDPOINT}/stats`, {
        token: access_token,
        error: 'Error fetching links stats',
    })
}

export async function record_referral(page:string, user_id:number, client_ip:string) {
    return await api_status_is(API_ENDPOINT, {
        method: 'POST',
        body: {
            page: page,
            user_id: user_id,
            client_ip: client_ip,
        },
        error: 'Error recording referral',
    }, 201)
}
