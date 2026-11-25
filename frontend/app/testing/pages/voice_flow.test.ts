// @vitest-environment node
// (happy-dom drops the Cookie header from Request, and the pages read the voice session from it.)
//
// /voice shows one screen at a time, picked from the voice status: first-time
// setup until the pilot has a Mumble certificate, then just Connect.
import { experimental_AstroContainer as AstroContainer } from 'astro/container'
import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest'

import Page from '@/pages/voice.astro'
import StatusPartial from '@/pages/partials/voice_status_component.astro'
import ConnectPartial from '@/pages/partials/voice_connect_component.astro'
import ConnectedPartial from '@/pages/partials/voice_connected_component.astro'

const VOICE_COOKIE = 'voice_session=guest-voice-token'
const WINDOWS = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'

const fleet_access = {
    fleet_id: 7, branch: 1, branch_name: 'Fleet 1', placement: 'Mainline', commander: false,
    fleet_title: 'Amamake defence', start_time: '2026-11-24T19:00:00Z', fc_name: 'Liam Varn',
}

let status: Record<string, any>
let certificates: Record<string, any>[]

beforeEach(() => {
    status = {
        character_id: 1, character_name: 'Rhea', display_name: '[FL33T] Rhea', admitted: true, banned: false,
        reason: 'ok', community: true, fleets: [fleet_access], certificate_count: 0, signed_in_as: 'guest',
    }
    certificates = []
    vi.spyOn(console, 'log').mockImplementation(() => {})
    vi.spyOn(console, 'warn').mockImplementation(() => {})
    vi.stubGlobal('fetch', vi.fn(async (input: string, init?: RequestInit) => {
        const path = new URL(String(input).replace(/^"?DUMMY-VALUE"?/, 'http://api')).pathname
        if (path === '/api/voice/status') return new Response(JSON.stringify(status))
        if (path === '/api/voice/certificates') return new Response(JSON.stringify(certificates))
        if (path === '/api/voice/connect' && init?.method === 'POST')
            return new Response(JSON.stringify({ url: 'mumble://Rhea:secret@voice.example:64738/', expires_in_seconds: 120 }))
        return new Response('{}', { status: 404 })
    }))
})

afterEach(() => {
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
})

async function render(component: any, url: string, { cookie = VOICE_COOKIE, method = 'GET', user_agent = WINDOWS } = {}) {
    const container = await AstroContainer.create()
    return container.renderToResponse(component, {
        request: new Request(url, { method, headers: { cookie, 'user-agent': user_agent } }),
    })
}

const STATUS_URL = 'http://localhost:4321/partials/voice_status_component/'

describe('the voice flow partial', () => {
    test('a pilot who never connected gets the setup, starting from their device', async () => {
        const html = await (await render(StatusPartial, STATUS_URL)).text()
        expect(html).toContain('Where will you use voice?')
        expect(html).toContain("device: 'windows'")
        expect(html).toContain('/images/mumble-logo.svg')
        expect(html).toContain('Amamake defence')
        expect(html).toContain('hx-trigger="voice-connected from:body"')
        expect(html).not.toContain('Ready when you are')
    })

    test('a pilot with a certificate sees only Connect', async () => {
        status.certificate_count = 1
        certificates = [{ id: 3, fingerprint: 'ab', created_at: '2026-11-01T00:00:00Z', last_used_at: null }]
        const html = await (await render(StatusPartial, STATUS_URL)).text()
        expect(html).toContain('Ready when you are')
        expect(html).not.toContain('Where will you use voice?')
        expect(html).toContain('hx-trigger="submit"')
    })

    test('"Sign in and connect" opens Mumble on load', async () => {
        status.certificate_count = 1
        const html = await (await render(StatusPartial, `${STATUS_URL}?connect=1`)).text()
        expect(html).toContain('hx-trigger="submit, load"')
    })

    test('an alt is offered a one-click switch', async () => {
        Object.assign(status, { admitted: false, reason: 'not_main', fleets: [] })
        const html = await (await render(StatusPartial, STATUS_URL)).text()
        expect(html).toContain('Sign in with your main')
        expect(html).toContain('/voice/sign-in?switch=1')
    })

    test('no fleet yet: checks again every 30 seconds and offers to set up meanwhile', async () => {
        Object.assign(status, { admitted: false, reason: 'no_access', fleets: [] })
        const html = await (await render(StatusPartial, STATUS_URL)).text()
        expect(html).toContain('Join a fleet to get into voice')
        expect(html).toContain('hx-trigger="every 30s"')
        expect(html).toContain('view=setup')
    })

    test('a ban wins over any view', async () => {
        Object.assign(status, { admitted: false, banned: true, reason: 'banned', fleets: [] })
        const html = await (await render(StatusPartial, `${STATUS_URL}?view=keys`)).text()
        expect(html).toContain('join fleet voice')
        expect(html).not.toContain('Set up your keys')
    })

    test('the key guide shows the broadcast key to commanders only', async () => {
        status.certificate_count = 1
        const pilot = await (await render(StatusPartial, `${STATUS_URL}?view=keys`)).text()
        expect(pilot).toContain('in Fleet 1 · Mainline')
        expect(pilot).toContain('Report to FCs')
        expect(pilot).not.toContain('Broadcast to the fleet')
        status.fleets = [{ ...fleet_access, commander: true }]
        const fc = await (await render(StatusPartial, `${STATUS_URL}?view=keys`)).text()
        expect(fc).toContain('Broadcast to the fleet')
    })
})

describe('connect', () => {
    test('opens the link straight away and starts watching for the pilot', async () => {
        const html = await (await render(ConnectPartial, 'http://localhost:4321/partials/voice_connect_component/', { method: 'POST' })).text()
        expect(html).toContain('data-url="mumble://Rhea:secret@voice.example:64738/"')
        expect(html).toContain('window.location.href = $el.dataset.url')
        expect(html).toContain('/partials/voice_connected_component/?since=')
    })

    test('the watcher tells the page once a certificate is used after Connect', async () => {
        const since = new Date(Date.now() - 20_000).toISOString()
        const url = `http://localhost:4321/partials/voice_connected_component/?since=${encodeURIComponent(since)}`

        certificates = [{ id: 1, fingerprint: 'ab', created_at: '2026-01-01T00:00:00Z', last_used_at: '2026-01-02T00:00:00Z' }]
        const waiting = await render(ConnectedPartial, url)
        expect(waiting.headers.get('hx-trigger')).toBeNull()
        expect(await waiting.text()).toContain('hx-trigger="load delay:5s"')

        certificates = [{ id: 1, fingerprint: 'ab', created_at: '2026-01-01T00:00:00Z', last_used_at: new Date().toISOString() }]
        const arrived = await render(ConnectedPartial, url)
        expect(arrived.headers.get('hx-trigger')).toBe('voice-connected')
        expect(await arrived.text()).not.toContain('hx-trigger')
    })

    test('the watcher stops after a few minutes', async () => {
        const since = new Date(Date.now() - 10 * 60_000).toISOString()
        const response = await render(ConnectedPartial, `http://localhost:4321/partials/voice_connected_component/?since=${encodeURIComponent(since)}`)
        expect((await response.text()).trim()).toBe('')
    })
})

describe('the signed-out page', () => {
    test('a first-time visitor is asked to sign in with EVE', async () => {
        const html = await (await render(Page, 'http://localhost:4321/voice', { cookie: '' })).text()
        expect(html).toContain('Sign in with your main')
        expect(html).not.toContain('then=connect')
    })

    test('a browser that connected before gets "Sign in and connect"', async () => {
        const html = await (await render(Page, 'http://localhost:4321/voice', { cookie: 'voice_returning=1' })).text()
        expect(html).toContain('/voice/sign-in?then=connect')
        expect(html).not.toContain('Sign in with your main')
    })
})
