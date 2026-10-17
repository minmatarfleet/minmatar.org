import type { CreatorAccount } from '@dtypes/api.minmatar.org'
import { api_request } from '@helpers/api.minmatar.org/client'

const API_ENDPOINT = `${import.meta.env.API_URL}/api/creators`

export async function get_my_creator_accounts(
    access_token: string,
): Promise<CreatorAccount[]> {
    return await api_request<CreatorAccount[]>(API_ENDPOINT, {
        token: access_token,
        error: 'Error fetching creator accounts',
    })
}
