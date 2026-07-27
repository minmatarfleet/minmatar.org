import type { User } from '@dtypes/jwt'
import * as jose from 'jose'
import { HTTP_403_Forbidden } from '@helpers/http_responses'

const API_ENDPOINT = `${import.meta.env.API_URL}/api/freight`

export async function GET({ cookies }) {
    const auth_token = cookies.has('auth_token')
        ? cookies.get('auth_token').value
        : false
    const user: User | false = auth_token
        ? jose.decodeJwt(auth_token) as User
        : false

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
