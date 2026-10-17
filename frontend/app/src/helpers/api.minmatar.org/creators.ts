import type { CreatorAccount } from '@dtypes/api.minmatar.org'
import { api_request, api_response } from '@helpers/api.minmatar.org/client'

const API_ENDPOINT = `${import.meta.env.API_URL}/api/creators`

export async function get_my_creator_accounts(
    access_token: string,
): Promise<CreatorAccount[]> {
    return await api_request<CreatorAccount[]>(API_ENDPOINT, {
        token: access_token,
        error: 'Error fetching creator accounts',
    })
}

export async function set_reddit_username(access_token: string, username: string) {
    await api_response(`${API_ENDPOINT}/reddit`, {
        method: 'PUT',
        token: access_token,
        body: { username },
    })
}
