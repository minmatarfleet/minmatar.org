import { get_request_user } from '@helpers/request_user'
import type { APIContext } from 'astro'
import { get_internal_api_url } from '@helpers/env'

const API_URL = get_internal_api_url()

export async function PATCH({ params, request, cookies, locals }: APIContext) {
    const { auth_token } = get_request_user({ cookies, locals })

    const headers: Record<string, string> = {
        'Content-Type': 'application/json',
    }
    if (auth_token)
        headers.Authorization = `Bearer ${auth_token}`

    const body = await request.text()
    const upstream = await fetch(
        `${API_URL}/api/industry/loyalty/orders/${params.order_id}`,
        {
            method: 'PATCH',
            headers,
            body,
        },
    )

    const data = await upstream.text()
    return new Response(data, {
        status: upstream.status,
        headers: { 'Content-Type': 'application/json' },
    })
}
