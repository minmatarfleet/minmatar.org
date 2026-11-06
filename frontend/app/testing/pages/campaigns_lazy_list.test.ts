// @vitest-environment node
// (happy-dom drops the Cookie header from Request, and the page reads auth_token from it.)
//
// /campaigns/ answers without waiting for the campaigns call: the list loads
// through /partials/campaign_list_component behind a skeleton.
import { experimental_AstroContainer as AstroContainer } from 'astro/container'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import * as jose from 'jose'

import Page from '@/pages/campaigns/index.astro'
import Partial from '@/pages/partials/campaign_list_component.astro'

const token = (is_superuser: boolean) =>
    new jose.UnsecuredJWT({ user_id: 1, username: 'pilot', is_superuser }).encode()

let requested: string[] = []
let campaigns_status = 200

beforeEach(() => {
    requested = []
    campaigns_status = 200
    vi.spyOn(console, 'log').mockImplementation(() => {})
    vi.spyOn(console, 'warn').mockImplementation(() => {})
    vi.stubGlobal('fetch', vi.fn(async (input: string) => {
        const path = new URL(String(input).replace(/^"?DUMMY-VALUE"?/, 'http://api')).pathname
        requested.push(path)
        if (path === '/api/users/me/gates')
            return new Response(JSON.stringify({ features: [], legacy: { permissions: [] }, gate_source: 'legacy', led_corporations: [] }))
        if (path === '/api/campaigns' || path === '/api/campaigns/')
            return new Response(campaigns_status === 200 ? '[]' : '{"detail":"boom"}', { status: campaigns_status })
        return new Response('{}', { status: 404 })
    }))
})

afterEach(() => {
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
})

async function render(component: any, url: string, cookie?: string) {
    const container = await AstroContainer.create()
    return container.renderToResponse(component, {
        request: new Request(url, { headers: cookie ? { cookie } : {} }),
    })
}

test('the page renders the skeleton and the partial slot without calling the campaigns API', async () => {
    const response = await render(Page, 'http://localhost:4321/campaigns/', `auth_token=${token(true)}`)
    const html = await response.text()

    expect(response.status).toBe(200)
    expect(html).toContain('hx-get="/partials/campaign_list_component"')
    expect(html).toContain('hx-swap="outerHTML"')
    expect(html).toContain('campaign-list-skeleton')
    expect(requested.some((path) => path.startsWith('/api/campaigns'))).toBe(false)
})

test('the page still sends a signed-out visitor to log in', async () => {
    const response = await render(Page, 'http://localhost:4321/campaigns/')

    expect(response.status).toBeGreaterThanOrEqual(300)
    expect(response.status).toBeLessThan(400)
})

test('the page still refuses a pilot without campaigns.view', async () => {
    const response = await render(Page, 'http://localhost:4321/campaigns/', `auth_token=${token(false)}`)

    expect(response.status).toBe(403)
})

test('the partial renders ErrorRefetch (the backend error) when the campaigns call fails', async () => {
    campaigns_status = 502
    const response = await render(Partial, 'http://localhost:4321/partials/campaign_list_component', `auth_token=${token(true)}`)
    const html = await response.text()

    expect(response.status).toBe(200)
    expect(html).toContain('Error fetching campaigns: boom')
    expect(html).not.toContain('campaign-list-skeleton')
})
