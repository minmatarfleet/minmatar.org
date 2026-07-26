import type { APIContext } from 'astro'

const API_URL = import.meta.env.API_URL

export async function GET({ params, cookies }: APIContext) {
    const auth_token = cookies.has('auth_token')
        ? cookies.get('auth_token')?.value
        : null

    const key = params.key
    if (!key) {
        return new Response(JSON.stringify({ detail: 'Missing facility key' }), {
            status: 400,
            headers: { 'Content-Type': 'application/json' },
        })
    }

    const headers: Record<string, string> = {
        'Content-Type': 'application/json',
    }
    if (auth_token)
        headers.Authorization = `Bearer ${auth_token}`

    const upstream = await fetch(
        `${API_URL}/api/industry/planner/facilities/${encodeURIComponent(key)}`,
        { headers },
    )

    const data = await upstream.text()
    return new Response(data, {
        status: upstream.status,
        headers: { 'Content-Type': 'application/json' },
    })
}
