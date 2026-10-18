import { get_request_user } from '@helpers/request_user'
import { HTTP_403_Forbidden } from '@helpers/http_responses'
import { get_internal_api_url } from '@helpers/env'

const API_ENDPOINT = `${get_internal_api_url()}/api/freight`

export async function GET({ cookies, locals }) {
    const { auth_token, user } = get_request_user({ cookies, locals })

    if (!auth_token || !user)
        return HTTP_403_Forbidden()

    const response = await fetch(`${API_ENDPOINT}/contracts/history/csv`, {
        headers: {
            Authorization: `Bearer ${auth_token}`,
        },
    })

    if (!response.ok) {
        return new Response(
            `Failed to download freight contracts CSV (${response.status})`,
            { status: response.status },
        )
    }

    const stamp = new Date().toISOString().slice(0, 10).replaceAll('-', '')
    const body = await response.arrayBuffer()

    return new Response(body, {
        status: 200,
        headers: {
            'Content-Type': 'text/csv; charset=utf-8',
            'Content-Disposition': `attachment; filename="freight-contracts-history-${stamp}.csv"`,
        },
    })
}
