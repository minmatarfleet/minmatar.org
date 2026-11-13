// @vitest-environment node
// (happy-dom drops the Cookie header from Request, and the page reads auth_token from it.)
//
// /learning/ (the Certificates tab) makes its personal calls in two rounds
// instead of one after another. These render the real page against a routed
// fetch and fail one call at a time: each failure must leave the same parts
// empty as the old sequential code did. Skill plans moved to their own tab, so
// this page never asks for them.
import { experimental_AstroContainer as AstroContainer } from 'astro/container'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import * as jose from 'jose'

import Page from '@/pages/learning/index.astro'

const AUTH_TOKEN = new jose.UnsecuredJWT({ user_id: 1, username: 'pilot', is_superuser: false }).encode()
const PRIMARY_ID = 2112000001
const READINESS_ID = 2112000009

const ROUTES: Record<string, unknown> = {
    '/api/users/me/gates': {
        features: [],
        legacy: { permissions: ['eveonline.add_evecharactertag', 'learning.change_certificate', 'eveonline.change_eveskillset'] },
        gate_source: 'legacy',
        led_corporations: [],
    },
    '/api/learning/me': { persona: 'alliance', persona_confirmed: true, completed_learning_slugs: [] },
    '/api/learning/persona/recommendation': { persona: 'alliance' },
    '/api/learning/certificates': [],
    '/api/eveonline/characters/summary': { characters: [{ character_id: READINESS_ID, character_name: 'Readiness Main', is_primary: true }] },
    [`/api/eveonline/characters/${READINESS_ID}/tokens`]: [],
    '/api/eveonline/characters/primary': { character_id: PRIMARY_ID, character_name: 'Primary Pilot' },
    [`/api/eveonline/characters/${PRIMARY_ID}`]: { character_id: PRIMARY_ID, character_name: 'Primary Pilot' },
    [`/api/eveonline/characters/${PRIMARY_ID}/skillsets`]: [{ name: 'Rifter Basics', progress: 0.5, missing_skills: [] }],
}

let failing = new Set<string>()
let requested: string[] = []

beforeEach(() => {
    failing = new Set()
    requested = []
    vi.spyOn(console, 'log').mockImplementation(() => {})
    vi.spyOn(console, 'warn').mockImplementation(() => {})
    vi.spyOn(console, 'error').mockImplementation(() => {})
    vi.stubGlobal('fetch', vi.fn(async (input: string) => {
        const path = new URL(String(input).replace(/^"?DUMMY-VALUE"?/, 'http://api')).pathname
        requested.push(path)
        if (failing.has(path)) return new Response('{"detail":"boom"}', { status: 500 })
        if (path in ROUTES) return new Response(JSON.stringify(ROUTES[path]), { status: 200 })
        return new Response('{}', { status: 404 })
    }))
})

afterEach(() => {
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
})

async function render() {
    const container = await AstroContainer.create()
    return container.renderToString(Page, {
        request: new Request('http://localhost:4321/learning/', { headers: { cookie: `auth_token=${AUTH_TOKEN}` } }),
    })
}

function parts(html: string) {
    return {
        readiness: html.includes(`/account/tags/${READINESS_ID}`),
        certificates_admin: html.includes('aria-label="Manage certificates and guides"'),
        certificates_error: html.includes('Could not load certificates'),
    }
}

const ALL = { readiness: true, certificates_admin: true, certificates_error: false }
const NO_PERSONAL = { readiness: false, certificates_admin: false, certificates_error: false }

test('with every call answering, every part renders', async () => {
    expect(parts(await render())).toEqual(ALL)
})

test('the Certificates tab does not load skill plans or the primary character', async () => {
    const html = await render()
    expect(html).not.toContain('Rifter Basics')
    expect(requested).not.toContain('/api/eveonline/characters/primary')
    expect(requested).not.toContain(`/api/eveonline/characters/${PRIMARY_ID}/skillsets`)
})

test('a learning/me failure leaves readiness and the admin link empty, as before', async () => {
    failing.add('/api/learning/me')
    expect(parts(await render())).toEqual(NO_PERSONAL)
    expect(requested).not.toContain('/api/eveonline/characters/summary')
    expect(requested).toContain('/api/learning/certificates')
})

test('a recommendation failure leaves the same parts empty, as before', async () => {
    failing.add('/api/learning/persona/recommendation')
    expect(parts(await render())).toEqual(NO_PERSONAL)
})

test('a readiness summary failure also hides the admin link, as before', async () => {
    failing.add('/api/eveonline/characters/summary')
    expect(parts(await render())).toEqual(NO_PERSONAL)
})

test('a certificates failure shows the certificates error and nothing else changes', async () => {
    failing.add('/api/learning/certificates')
    expect(parts(await render())).toEqual({ ...ALL, certificates_error: true })
})

test('the personal calls run in two rounds: summary and certificates start before either answers', async () => {
    const order: string[] = []
    const gates: Record<string, () => void> = {}
    vi.stubGlobal('fetch', vi.fn((input: string) => {
        const path = new URL(String(input).replace(/^"?DUMMY-VALUE"?/, 'http://api')).pathname
        order.push(path)
        const respond = () => new Response(JSON.stringify(ROUTES[path] ?? {}), { status: path in ROUTES ? 200 : 404 })
        if (['/api/eveonline/characters/summary', '/api/learning/certificates'].includes(path))
            return new Promise((resolve) => { gates[path] = () => resolve(respond()) })
        return Promise.resolve(respond())
    }))

    const html = render()
    await vi.waitFor(() => expect(Object.keys(gates).sort()).toEqual([
        '/api/eveonline/characters/summary',
        '/api/learning/certificates',
    ].sort()))
    Object.values(gates).forEach((open) => open())
    expect(parts(await html)).toEqual(ALL)
})
