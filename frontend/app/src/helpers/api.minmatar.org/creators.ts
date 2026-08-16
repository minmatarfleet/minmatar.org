import type { CreatorAccount } from '@dtypes/api.minmatar.org'
import { get_error_message } from '@helpers/string'

const API_ENDPOINT = `${import.meta.env.API_URL}/api/creators`

export async function get_my_creator_accounts(
    access_token: string,
): Promise<CreatorAccount[]> {
    const ENDPOINT = API_ENDPOINT
    console.log(`Requesting: ${ENDPOINT}`)
    try {
        const response = await fetch(ENDPOINT, {
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${access_token}`,
            },
        })
        if (!response.ok) {
            throw new Error(
                get_error_message(response.status, `GET ${ENDPOINT}`),
                { cause: response.status },
            )
        }
        return await response.json() as CreatorAccount[]
    } catch (error) {
        throw new Error(`Error fetching creator accounts: ${(error as Error).message}`)
    }
}
