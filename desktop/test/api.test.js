const { test } = require('node:test')
const assert = require('node:assert/strict')
const { ApiClient, ApiError, client_id, load_upcoming_fleets, load_campaign } = require('../src/main/api')
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

test('names the app and its version on every request, signed in or not', async () => {
    const seen = []
    const api = new ApiClient({
        api_url: 'https://api.example',
        get_token: () => 'jwt',
        client: client_id({ version: '1.2.3', portable: true }),
        fetch_impl: async (url, options) => {
            seen.push(options.headers['X-Minmatar-Client'])
            return { ok: true, status: 200, json: async () => ({}) }
        },
    })
    await api.me()
    await api.intel_map()   // unauthenticated
    await api.save_desktop_settings({ locked: true })
    assert.deepEqual(seen, ['desktop/1.2.3 (portable)', 'desktop/1.2.3 (portable)', 'desktop/1.2.3 (portable)'])
    assert.equal(client_id({ version: '0.10.0' }), 'desktop/0.10.0 (installer)')
})

test('main.js reads the client version from the running app', () => {
    const source = require('fs').readFileSync(require.resolve('../src/main/main.js'), 'utf8')
    assert.match(source, /client_id\(\{ version: app\.getVersion\(\)/)
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

test('a backend that names FCs and doctrines needs one request for the schedule', async () => {
    const calls = []
    const named = FLEETS.map(fleet => ({
        ...fleet,
        fleet_commander_character_id: fleet.fleet_commander === 10 ? 9001 : null,
        fleet_commander_name: fleet.fleet_commander === 10 ? 'FC One' : null,
        doctrine_name: fleet.doctrine_id === 5 ? 'Hurricanes' : null,
    }))
    const api = new ApiClient({
        api_url: 'https://api.example',
        get_token: () => 'jwt',
        fetch_impl: fake_fetch({
            '/api/fleets/v3?fleet_filter=active': named,
            '/api/users/profiles?ids=11': PROFILES.filter(p => p.user_id === 11),
        }, calls),
    })
    const rows = await load_upcoming_fleets(api, 'https://web.example')
    // FC 11 has no primary character, so only that profile is looked up (for the username).
    assert.deepEqual(calls.map(c => c.url.replace('https://api.example', '')), ['/api/fleets/v3?fleet_filter=active', '/api/users/profiles?ids=11'])
    // Same rows as the old join builds.
    const old_api = new ApiClient({
        api_url: 'https://api.example',
        get_token: () => 'jwt',
        fetch_impl: fake_fetch({
            '/api/fleets/v3?fleet_filter=active': FLEETS,
            '/api/users/profiles?ids=11,10': PROFILES,
            '/api/doctrines/5': { id: 5, name: 'Hurricanes' },
        }),
    })
    assert.deepEqual(rows, await load_upcoming_fleets(old_api, 'https://web.example'))
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

const OVERLAY = {
    campaign: {
        slug: 'bleak-lands-push',
        name: 'Bleak Lands Push',
        week_index: 3,
        week_count: 6,
        systems: [
            { system_id: 1, name: 'Kamela', solar_system_id: 30003069, priority: 'high', holder: 'amarr', objective: 'capture_complexes', objective_label: 'Capture complexes', progress_percent: 62, change_week: 22, change_24h: 8, flipped: null, detail: '1,860 of 3,000 victory points' },
            { system_id: 2, name: 'Auga', solar_system_id: 30002075, priority: 'low', holder: 'caldari', objective: 'hold_advantage', objective_label: 'Hold advantage', progress_percent: null, change_week: null, change_24h: null, flipped: 'lost', detail: '' },
        ],
        active_window_minutes: 60,
        active_pilots: [
            { character_id: 3002, character_name: 'Pilot Main', system: 'Kamela', last_at: '2026-10-16T17:57:00Z', kills: 2, losses: 0, complexes: 0, advantage_sites: 0, in_fleet: true },
        ],
    },
}

test('campaign overlay -> window model, with a link we build ourselves', async () => {
    const calls = []
    const api = new ApiClient({ api_url: 'https://api.example', get_token: () => 'jwt', fetch_impl: fake_fetch({ '/api/campaigns/overlay': OVERLAY }, calls) })
    const campaign = await load_campaign(api, 'https://web.example')
    assert.equal(calls[0].auth, 'Bearer jwt')
    assert.equal(campaign.url, 'https://web.example/campaigns/bleak-lands-push')
    assert.deepEqual(campaign.systems.map(s => [s.name, s.objective, s.progress, s.change, s.change_period, s.change_24h, s.flipped]), [
        ['Kamela', 'Capture complexes', 62, 22, 'week', 8, null],
        ['Auga', 'Hold advantage', null, null, 'week', null, 'lost'],
    ])
    assert.equal(campaign.systems[0].holder, 'amarr')
    assert.equal(campaign.systems[1].holder, null)   // only the two militias have a logo
    assert.equal(campaign.pilots[0].name, 'Pilot Main')
    assert.equal(campaign.pilots[0].in_fleet, true)
})

test('a backend from before the weekly move still draws the day\'s', async () => {
    const old = { campaign: { ...OVERLAY.campaign, systems: [{ system_id: 1, name: 'Kamela', solar_system_id: 30003069, holder: 'amarr', objective: 'capture_complexes', objective_label: 'Capture complexes', progress_percent: 62, change_24h: 8, detail: '' }] } }
    const api = new ApiClient({ api_url: 'https://api.example', get_token: () => 'jwt', fetch_impl: fake_fetch({ '/api/campaigns/overlay': old }) })
    const [system] = (await load_campaign(api, 'https://web.example')).systems
    assert.deepEqual([system.change, system.change_period, system.flipped], [8, '24h', null])
})

test('no live campaign -> null; no access -> 403 for the window to explain', async () => {
    const none = new ApiClient({ api_url: 'https://api.example', get_token: () => 'jwt', fetch_impl: fake_fetch({ '/api/campaigns/overlay': { campaign: null } }) })
    assert.equal(await load_campaign(none, 'https://web.example'), null)
    const denied = new ApiClient({ api_url: 'https://api.example', get_token: () => 'jwt', fetch_impl: fake_fetch({ '/api/campaigns/overlay': 403 }) })
    await assert.rejects(load_campaign(denied, 'https://web.example'), err => err.status === 403)
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

test('polled fleet windows send If-None-Match and reuse the body on 304', async () => {
    const seen = []
    let status = 200
    const api = new ApiClient({
        api_url: 'https://api.example',
        get_token: () => 'jwt',
        fetch_impl: async (url, options) => {
            seen.push(options.headers['If-None-Match'] || null)
            if (status === 304) return { ok: false, status: 304, headers: { get: () => '"v1"' }, json: async () => { throw new Error('no body') } }
            return { ok: true, status: 200, headers: { get: name => (name === 'etag' ? '"v1"' : null) }, json: async () => ({ window: { mode: 'fc' } }) }
        },
    })
    const first = await api.current_fleet_window()
    assert.deepEqual(first, { body: { window: { mode: 'fc' } }, changed: true })
    status = 304
    const second = await api.current_fleet_window()
    assert.deepEqual(second, { body: { window: { mode: 'fc' } }, changed: false })
    assert.deepEqual(seen, [null, '"v1"'])

    api.forget_cached()
    status = 200
    await api.current_fleet_window()
    assert.equal(seen.at(-1), null)
})

test('ship sign-up sends one selection for the composition key', async () => {
    const sent = []
    const api = new ApiClient({
        api_url: 'https://api.example',
        get_token: () => 'jwt',
        fetch_impl: async (url, options) => {
            sent.push({ url, method: options.method, body: JSON.parse(options.body) })
            return { ok: true, status: 200, json: async () => [] }
        },
    })
    await api.set_my_ship(7, 1001, 'm:12')
    assert.deepEqual(sent, [{ url: 'https://api.example/api/fleets/7/my-ship-volunteers', method: 'PUT', body: { selections: [{ character_id: 1001, fitting_id: null, fleet_fitting_id: 12 }] } }])
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
