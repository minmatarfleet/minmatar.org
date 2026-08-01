import type { APIContext } from 'astro'

const API_URL = import.meta.env.API_URL

export async function PATCH({ params, request, cookies }: APIContext) {
    const auth_token = cookies.has('auth_token')
        ? cookies.get('auth_token')?.value
        : null

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
