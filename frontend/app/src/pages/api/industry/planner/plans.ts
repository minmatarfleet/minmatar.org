import type { APIContext } from 'astro'

const API_URL = import.meta.env.API_URL

export async function POST({ request, cookies }: APIContext) {
    const auth_token = cookies.has('auth_token')
        ? cookies.get('auth_token')?.value
        : null
    if (!auth_token) {
        return new Response(JSON.stringify({ detail: 'Unauthorized' }), {
            status: 401,
            headers: { 'Content-Type': 'application/json' },
        })
    }

    const body = await request.text()
    const upstream = await fetch(`${API_URL}/api/industry/planner/plans`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${auth_token}`,
        },
        body,
    })

    const data = await upstream.text()
    return new Response(data, {
        status: upstream.status,
        headers: { 'Content-Type': 'application/json' },
    })
}
