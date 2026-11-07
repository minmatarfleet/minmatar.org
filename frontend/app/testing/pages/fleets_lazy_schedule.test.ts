// @vitest-environment node
// (happy-dom drops the Cookie header from Request, and the page reads auth_token from it.)
//
// /fleets/upcoming/ answers without waiting for the fleet schedule: the list
// loads through /partials/upcoming_fleets_initial_component/ behind a
// skeleton, and fades the cover to a live fleet's location.
import { experimental_AstroContainer as AstroContainer } from 'astro/container'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import * as jose from 'jose'

import Page from '@/pages/fleets/upcoming.astro'
import InitialPartial from '@/pages/partials/upcoming_fleets_initial_component.astro'
import RefreshPartial from '@/pages/partials/upcoming_fleets_component.astro'
import FleetListPartial from '@/pages/partials/fleet_list_component.astro'

const AUTH = `auth_token=${new jose.UnsecuredJWT({ user_id: 1, username: 'pilot', is_superuser: true }).encode()}`
const AMAMAKE = 'Amamake - 5 times nearly AT winners'

const in_hours = (h: number) => new Date(Date.now() + h * 3_600_000).toISOString()
const fleet = (id: number, extra: Record<string, unknown> = {}) => ({
    id,
    fleet_commander: 1,
    fleet_commander_character_id: 100 + id,
    fleet_commander_name: `FC ${id}`,
    start_time: in_hours(id),
    status: 'pending',
    type: 'strategic',
    location: AMAMAKE,
    ...extra,
})
const LIVE = fleet(1, { status: 'active', start_time: in_hours(-1), tracking: { id: 9, start_time: in_hours(-1), end_time: null } })
const NEXT = fleet(2)

let fleets: unknown[] = []
let fail_fleets = false
let requested: string[] = []

beforeEach(() => {
    fleets = [NEXT]
    fail_fleets = false
    requested = []
    vi.spyOn(console, 'log').mockImplementation(() => {})
    vi.spyOn(console, 'warn').mockImplementation(() => {})
    vi.spyOn(console, 'error').mockImplementation(() => {})
    vi.stubGlobal('fetch', vi.fn(async (input: string) => {
        const path = new URL(String(input).replace(/^"?DUMMY-VALUE"?/, 'http://api')).pathname
        requested.push(path)
        const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status })
        if (path === '/api/users/me/gates')
            return json({ features: [], legacy: { permissions: [] }, gate_source: 'legacy', led_corporations: [] })
        if (path === '/api/fleets/v3')
            return fail_fleets ? json({ detail: 'fleets down' }, 502) : json(fleets)
        if (path === '/api/fleets/audiences') return json([])
        if (path === '/api/eveonline/characters/summary') return json({ characters: [] })
        if (path.startsWith('/api/fleets/')) return json([])
        return json({}, 404)
    }))
})

afterEach(() => {
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
})

async function render(component: any, url: string, cookie = AUTH) {
    const container = await AstroContainer.create()
    const response = await container.renderToResponse(component, { request: new Request(url, { headers: { cookie } }) })
    return { response, html: await response.text() }
}

test('the page shell does not wait for the schedule and loads it behind the skeleton', async () => {
    const { response, html } = await render(Page, 'http://localhost:4321/fleets/upcoming/')

    expect(response.status).toBe(200)
    expect(html).toContain('hx-get="/partials/upcoming_fleets_initial_component/"')
    expect(html).toContain('fleet-schedule-skeleton')
    expect(requested.filter((p) => p.startsWith('/api/fleets/') && p !== '/api/fleets/audiences')).toEqual([])
})

test('the page passes its host filter to the partial', async () => {
    const { html } = await render(Page, 'http://localhost:4321/fleets/upcoming/?host=alliance')

    expect(html).toContain('hx-get="/partials/upcoming_fleets_initial_component/?host=alliance"')
})

test('the page still shows the flash-form error alert', async () => {
    // The container returns no Set-Cookie headers; the cookie deletion is
    // checked against the running servers in the PR's harness.
    const { html } = await render(Page, 'http://localhost:4321/fleets/upcoming/', `${AUTH}; flash_form_error=Ping%20failed`)

    expect(html).toContain('Ping failed')
})

test('the page still refuses a pilot without fleets.view', async () => {
    const pilot = `auth_token=${new jose.UnsecuredJWT({ user_id: 2, username: 'p', is_superuser: false }).encode()}`
    const { response } = await render(Page, 'http://localhost:4321/fleets/upcoming/', pilot)

    expect(response.status).toBe(403)
})

test('the first load renders the schedule without the refresh label, and no cover swap without a live fleet', async () => {
    const { html } = await render(InitialPartial, 'http://localhost:4321/partials/upcoming_fleets_initial_component/')

    expect(html).toContain('fleet-spotlight')
    expect(html).not.toContain('timeago_span')
    expect(html).not.toContain('/partials/fleet_cover')
})

test('the first load with a live fleet fades the cover to its location', async () => {
    fleets = [LIVE, NEXT]
    const { html } = await render(InitialPartial, 'http://localhost:4321/partials/upcoming_fleets_initial_component/')

    expect(html).toContain(`hx-get="/partials/fleet_cover?location_name=${encodeURIComponent(AMAMAKE)}"`)
    expect(html).toContain('hx-target="#viewport-cover-oob"')
})

test('the first load shows ErrorRefetch when the schedule fails', async () => {
    fail_fleets = true
    const { response, html } = await render(InitialPartial, 'http://localhost:4321/partials/upcoming_fleets_initial_component/?host=tribe')

    expect(response.status).toBe(200)
    expect(html).toContain('fleets down')
    expect(html).not.toContain('fleet-spotlight')
})

test('the first load refuses a pilot without fleets.view, like the refresh partial', async () => {
    const pilot = `auth_token=${new jose.UnsecuredJWT({ user_id: 2, username: 'p', is_superuser: false }).encode()}`
    const { response } = await render(InitialPartial, 'http://localhost:4321/partials/upcoming_fleets_initial_component/', pilot)

    expect(response.status).toBe(403)
})

test('the 240s refresh is unchanged: refresh label, and a 500 on failure', async () => {
    const ok = await render(RefreshPartial, 'http://localhost:4321/partials/upcoming_fleets_component/')
    expect(ok.html).toContain('timeago_span')

    fail_fleets = true
    const failed = await render(RefreshPartial, 'http://localhost:4321/partials/upcoming_fleets_component/')
    expect(failed.response.status).toBe(500)
})

test('fleet_list_component keeps the host filter, for the list and its retry URL', async () => {
    fleets = [NEXT, fleet(3, { host_group: { id: 5, tribe_id: 3, name: 'G' } })]
    const { html } = await render(FleetListPartial, 'http://localhost:4321/partials/fleet_list_component?upcoming=true&host=tribe')

    expect(html).toContain('FC 3')
    expect(html).not.toContain('FC 2')
})
