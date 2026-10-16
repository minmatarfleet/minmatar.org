const { test } = require('node:test')
const assert = require('node:assert/strict')
const { ApiClient, ApiError, load_upcoming_fleets } = require('../src/main/api')
const { load_config } = require('../src/main/config')

function fake_fetch(routes, calls = []) {
    return async (url, options) => {
        calls.push({ url, auth: options.headers.Authorization })
        const path = url.replace('https://api.example', '')
        if (!(path in routes)) return { ok: false, status: 404, json: async () => ({ detail: 'nope' }) }
        const route = routes[path]
        if (typeof route === 'number') return { ok: false, status: route, json: async () => ({ detail: 'denied' }) }
        return { ok: true, status: 200, json: async () => route }
    }
}

const FLEETS = [
    { id: 2, type: 'non_strategic', audience: 'Alliance', description: 'Roam', start_time: '2026-10-17T20:00:00Z', fleet_commander: 11, doctrine_id: 5, location: 'Amamake', status: 'pending', tracking: null },
    { id: 1, type: 'strategic', audience: 'Alliance', description: 'Stratop', start_time: '2026-10-16T18:00:00Z', fleet_commander: 10, doctrine_id: null, location: 'Sosala', status: 'active', tracking: { id: 9 } },
    { id: 3, type: 'training', description: 'no fc', start_time: '2026-10-18T18:00:00Z', fleet_commander: null, location: '' },
]
const PROFILES = [
    { user_id: 10, username: 'fc_one', eve_character_profile: { character_id: 9001, character_name: 'FC One' } },
    { user_id: 11, username: 'fc_two', eve_character_profile: null },
]

test('sends the stored token as a Bearer header on authenticated calls only', async () => {
    const calls = []
    const api = new ApiClient({
        api_url: 'https://api.example',
        get_token: () => 'jwt',
        fetch_impl: fake_fetch({
            '/api/fleets/v3?fleet_filter=active': FLEETS,
            '/api/users/profiles?ids=11,10': PROFILES,
            '/api/doctrines/5': { id: 5, name: 'Hurricanes' },
        }, calls),
    })
    await load_upcoming_fleets(api, 'https://web.example')
    assert.equal(calls.find(c => c.url.includes('/fleets/v3')).auth, 'Bearer jwt')
    assert.equal(calls.find(c => c.url.includes('/profiles')).auth, undefined)
})

test('builds overlay rows: FC names, doctrine names, links, soonest first, no FC-less fleets', async () => {
    const api = new ApiClient({
        api_url: 'https://api.example',
        get_token: () => 'jwt',
        fetch_impl: fake_fetch({
            '/api/fleets/v3?fleet_filter=active': FLEETS,
            '/api/users/profiles?ids=11,10': PROFILES,
            '/api/doctrines/5': { id: 5, name: 'Hurricanes' },
        }),
    })
    const rows = await load_upcoming_fleets(api, 'https://web.example')
    assert.deepEqual(rows.map(r => r.id), [1, 2])
    assert.equal(rows[0].live, true)
    assert.equal(rows[0].fc_name, 'FC One')
    assert.equal(rows[0].fc_character_id, 9001)
    assert.equal(rows[0].type_label, 'Strategic')
    assert.equal(rows[0].doctrine, null)
    assert.equal(rows[1].fc_name, 'fc_two')
    assert.equal(rows[1].doctrine, 'Hurricanes')
    assert.equal(rows[1].url, 'https://web.example/fleets/upcoming/2')
})

test('API errors carry the HTTP status (401 -> sign in again, 403 -> no fleet access)', async () => {
    const api = new ApiClient({ api_url: 'https://api.example', get_token: () => 'jwt', fetch_impl: fake_fetch({ '/api/fleets/v3?fleet_filter=active': 403 }) })
    await assert.rejects(load_upcoming_fleets(api, 'https://web.example'), err => err instanceof ApiError && err.status === 403)
})

test('no token -> 401 without a network call', async () => {
    const calls = []
    const api = new ApiClient({ api_url: 'https://api.example', get_token: () => null, fetch_impl: fake_fetch({}, calls) })
    await assert.rejects(api.me(), err => err.status === 401)
    assert.equal(calls.length, 0)
})

test('a missing doctrine does not fail the list', async () => {
    const api = new ApiClient({
        api_url: 'https://api.example',
        get_token: () => 'jwt',
        fetch_impl: fake_fetch({ '/api/fleets/v3?fleet_filter=active': [FLEETS[0]], '/api/users/profiles?ids=11': PROFILES }),
    })
    const rows = await load_upcoming_fleets(api, 'https://web.example')
    assert.equal(rows[0].doctrine, null)
})

test('config defaults to production and accepts overrides', () => {
    assert.equal(load_config([], {}).api_url, 'https://api.minmatar.org')
    assert.equal(load_config([], {}).web_url, 'https://my.minmatar.org')
    assert.equal(load_config(['--api=http://localhost:8000/'], {}).api_url, 'http://localhost:8000')
    assert.equal(load_config([], { MINMATAR_API_URL: 'https://staging.example' }).api_url, 'https://staging.example')
})

test('desktop settings: GET with the token, PATCH sends only the given keys as JSON', async () => {
    const calls = []
    const api = new ApiClient({
        api_url: 'https://api.example',
        get_token: () => 'jwt',
        fetch_impl: async (url, options) => {
            calls.push({ url, method: options.method, auth: options.headers.Authorization, type: options.headers['Content-Type'], body: options.body, signal: options.signal })
            return { ok: true, status: 200, json: async () => ({ values: { show_sneak: false }, updated_at: null }) }
        },
    })
    assert.deepEqual((await api.desktop_settings()).values, { show_sneak: false })
    await api.save_desktop_settings({ show_sneak: false, 'window.fleets': null })
    assert.equal(calls[0].method, 'GET')
    assert.equal(calls[0].url, 'https://api.example/api/users/me/desktop-settings')
    assert.equal(calls[1].method, 'PATCH')
    assert.equal(calls[1].auth, 'Bearer jwt')
    assert.equal(calls[1].type, 'application/json')
    assert.deepEqual(JSON.parse(calls[1].body), { values: { show_sneak: false, 'window.fleets': null } })
    assert.ok(calls[1].signal, 'requests carry a timeout so a hung API never blocks settings')
})

test('intel calls: the map is public, shares are POSTed, and API errors keep their detail', async () => {
    const calls = []
    const api = new ApiClient({
        api_url: 'https://api.example',
        get_token: () => 'jwt',
        fetch_impl: async (url, options) => {
            calls.push({ url, method: options.method, auth: options.headers.Authorization, body: options.body })
            if (url.endsWith('/api/intel/reports')) return { ok: false, status: 400, json: async () => ({ detail: 'Pick the system this is from.' }) }
            return { ok: true, status: 200, json: async () => ({ systems: {}, edges: {} }) }
        },
    })
    await api.intel_map()
    assert.equal(calls[0].auth, undefined)
    await assert.rejects(api.intel_share({ text: 'Ardo Kesh', system: '' }), err => {
        assert.equal(err.status, 400)
        assert.equal(err.detail, 'Pick the system this is from.')
        return true
    })
    assert.equal(calls[1].method, 'POST')
    assert.deepEqual(JSON.parse(calls[1].body), { text: 'Ardo Kesh', kind: null, system: '', note: '', character_name: null })
})
