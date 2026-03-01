import type { APIContext } from 'astro'

const API_URL = import.meta.env.API_URL

export async function POST({ params, request, cookies }: APIContext) {
    const auth_token = cookies.has('auth_token') ? cookies.get('auth_token')?.value : null
    if (!auth_token) {
        return new Response(JSON.stringify({ detail: 'Unauthorized' }), { status: 401 })
    }

    const { tribe_id, group_id } = params
    const body = await request.text()

    const upstream = await fetch(
        `${API_URL}/api/tribes/${tribe_id}/groups/${group_id}/memberships`,
        {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${auth_token}`,
            },
            body,
        }
    )

    const data = await upstream.text()
    return new Response(data, {
        status: upstream.status,
        headers: { 'Content-Type': 'application/json' },
    })
}

export async function DELETE({ params, request, cookies }: APIContext) {
    const auth_token = cookies.has('auth_token') ? cookies.get('auth_token')?.value : null
    if (!auth_token) {
        return new Response(JSON.stringify({ detail: 'Unauthorized' }), { status: 401 })
    }

    const { tribe_id, group_id } = params
    const url = new URL(request.url)
    const membership_id = url.searchParams.get('membership_id')

    const upstream_url = membership_id
        ? `${API_URL}/api/tribes/${tribe_id}/groups/${group_id}/memberships/${membership_id}`
        : `${API_URL}/api/tribes/${tribe_id}/groups/${group_id}/memberships`

    const upstream = await fetch(upstream_url, {
        method: 'DELETE',
        headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${auth_token}`,
        },
    })

    const data = await upstream.text()
    return new Response(data || '{}', {
        status: upstream.status,
        headers: { 'Content-Type': 'application/json' },
    })
}
