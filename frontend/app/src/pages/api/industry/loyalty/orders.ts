import type { APIContext } from 'astro'
import { get_internal_api_url } from '@helpers/env'

const API_URL = get_internal_api_url()

export async function POST({ request, cookies }: APIContext) {
    const auth_token = cookies.has('auth_token')
        ? cookies.get('auth_token')?.value
        : null

    const headers: Record<string, string> = {
        'Content-Type': 'application/json',
    }
    if (auth_token)
        headers.Authorization = `Bearer ${auth_token}`

    const body = await request.text()
    const upstream = await fetch(`${API_URL}/api/industry/loyalty/orders`, {
        method: 'POST',
        headers,
        body,
    })

    const data = await upstream.text()
    return new Response(data, {
        status: upstream.status,
        headers: { 'Content-Type': 'application/json' },
    })
}
