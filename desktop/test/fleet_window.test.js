const { test } = require('node:test')
const assert = require('node:assert/strict')
const { FleetWindow, POLL_MS, MAX_BACKOFF_MS } = require('../src/main/fleet_window')
const { ApiError } = require('../src/main/api')

// A window payload as GET /api/fleets/window/current returns it (backend fleets/helpers/fleet_window.py).
function payload({ id = 7, mode = 'member', live = true, characters, loss = null, after_action = null, volunteers = {} } = {}) {
    return {
        mode,
        fleet: {
            id, type: 'strategic', type_label: 'Strategic', title: 'Hurricane Fleet', live,
            started_at: '2026-10-16T19:00:00Z', ended_at: live ? null : '2026-10-16T21:00:00Z', start_time: '2026-10-16T19:00:00Z',
            fc_character_id: 5000, fc_name: 'The FC', fc_system_id: 30002537, fc_system_name: 'Amamake',
            location_name: 'Amamake - Freeport', location_system_id: 30002537, location_system_name: 'Amamake',
        },
        counts: { in_fleet: 24, with_fc: 19, kills: 6, losses: 2, isk_destroyed: 1_420_000_000, isk_lost: 312_000_000 },
        ships: [
            { key: 'f:1', name: 'HFI', ship_type_id: 33157, ship_name: 'Hurricane Fleet Issue', role: 'primary', flying: 14, signed_up: 15 },
            { key: 'f:2', name: 'Scimitar', ship_type_id: 11978, ship_name: 'Scimitar', role: 'support', flying: 2, signed_up: 4 },
        ],
        roles: [{ role: 'logi', covered: true }, { role: 'cyno', covered: false }],
        needs: [],
        pilots: mode === 'fc' ? [{ character_id: 1 }] : [],
        attention: [],
        after_action,
        me: {
            character_ids: [1001, 1002],
            characters: characters || (mode === 'member' ? [
                { character_id: 1001, character_name: 'Kesra Lund', ship_type_id: 33157, ship_name: 'Hurricane Fleet Issue', solar_system_id: 30002053, solar_system_name: 'Hek', docked: false, doctrine: true, capsule: false },
            ] : []),
            ship_volunteers: volunteers,
            last_loss: loss,
        },
    }
}

// Fake timers: run what's due when the test says so.
function fake_timers() {
    let now = 0, next = 1
    const pending = new Map()
    return {
        now: () => now,
        timers: {
            setTimeout: (fn, ms) => { const id = next++; pending.set(id, { at: now + ms, fn }); return id },
            clearTimeout: id => pending.delete(id),
        },
        pending,
        due_in() { return Math.min(...[...pending.values()].map(t => t.at - now)) },
        async advance(ms) {
            now += ms
            for (const [id, t] of [...pending]) if (t.at <= now) { pending.delete(id); await t.fn() }
        },
    }
}

function setup({ current = null, opened = {}, fail = null } = {}) {
    const calls = []
    const clock = fake_timers()
    const copied = [], opened_urls = []
    const api = {
        current: current,
        async current_fleet_window() {
            calls.push('current')
            if (fail) throw fail
            return { body: { window: api.current }, changed: true }
        },
        async fleet_window(id) {
            calls.push(`window:${id}`)
            if (!(id in opened)) throw new ApiError(404, 'gone')
            return { body: opened[id], changed: true }
        },
        async fleet_composition(id) {
            calls.push(`composition:${id}`)
            return [{ key: 'f:2', eft_format: '[Scimitar, Logi]' }]
        },
        async set_my_ship(id, character_id, key) { calls.push(`sign-up:${id}:${character_id}:${key}`) },
        async refresh_motd(id) { calls.push(`motd:${id}`) },
    }
    const routes = { asked: [], async jumps(origin, destination) { routes.asked.push([origin, destination]); return 3 } }
    const fw = new FleetWindow({
        api, routes, web_url: 'https://web.example',
        clipboard: { writeText: text => copied.push(text) },
        open_external: url => opened_urls.push(url),
        now: clock.now, timers: clock.timers,
    })
    const snapshots = []
    fw.on('change', s => snapshots.push(s))
    return { fw, api, calls, clock, routes, copied, opened_urls, snapshots }
}

test('shows the list until the pilot is in a fleet, then the fleet', async () => {
    const t = setup()
    await t.fw.poll()
    assert.equal(t.snapshots.at(-1).view, 'list')

    t.api.current = payload()
    await t.fw.poll()
    const s = t.snapshots.at(-1)
    assert.equal(s.view, 'fleet')
    assert.equal(s.mode, 'member')
    assert.equal(s.you.character_name, 'Kesra Lund')
})

test('only publishes when something on screen changed', async () => {
    const t = setup({ current: payload() })
    await t.fw.poll()
    await t.fw.poll()
    await t.fw.poll()
    assert.equal(t.snapshots.length, 2)   // the route lookup lands once with the jump count, then nothing new
    assert.equal(t.snapshots.at(-1).jumps, 3)
})

test('polls every 30 s only while active, and catches up when shown again', async () => {
    const t = setup({ current: payload() })
    t.fw.set_active(true)
    await t.clock.advance(0)
    assert.deepEqual(t.calls, ['current'])
    assert.equal(t.clock.due_in(), POLL_MS)

    t.fw.set_active(false)
    assert.equal(t.clock.pending.size, 0)
    await t.clock.advance(10 * POLL_MS)
    assert.deepEqual(t.calls, ['current'])

    t.fw.set_active(true)   // data is stale: poll at once
    await t.clock.advance(0)
    assert.deepEqual(t.calls, ['current', 'current'])

    t.fw.set_active(false)
    await t.clock.advance(5_000)
    t.fw.set_active(true)   // fresh: wait out the rest of the interval
    assert.equal(t.clock.due_in(), POLL_MS - 5_000)
})

test('backs off while the API is down and caps the wait', async () => {
    const t = setup({ fail: new ApiError(502, 'down') })
    t.fw.set_active(true)
    await t.clock.advance(0)
    assert.equal(t.clock.due_in(), POLL_MS * 2)
    assert.match(t.snapshots.at(-1).error, /Retrying/)
    for (let i = 0; i < 6; i++) await t.clock.advance(t.clock.due_in())
    assert.equal(t.clock.due_in(), MAX_BACKOFF_MS)
})

test('a 401 signs out and stops polling', async () => {
    const t = setup({ fail: new ApiError(401, 'expired') })
    let signed_out = false
    t.fw.on('unauthorized', () => { signed_out = true })
    t.fw.set_active(true)
    await t.clock.advance(0)
    assert.equal(signed_out, true)
    assert.equal(t.clock.pending.size, 0)
})

test('back leaves the fleet until it changes; an opened fleet adds one call', async () => {
    const t = setup({ current: payload(), opened: { 9: payload({ id: 9, mode: 'viewer', live: false }) } })
    await t.fw.poll()
    t.fw.back()
    assert.equal(t.snapshots.at(-1).view, 'list')
    await t.fw.poll()
    assert.equal(t.snapshots.at(-1).view, 'list')

    await t.fw.open(9)
    assert.deepEqual(t.calls.slice(-2), ['current', 'window:9'])
    assert.equal(t.snapshots.at(-1).fleet.id, 9)
    t.fw.back()
    assert.equal(t.snapshots.at(-1).view, 'list')

    // The same fleet once it ends is a new state: the FC gets the after-action.
    t.api.current = payload({ mode: 'fc', live: false, after_action: { pilots: 30, duration_seconds: 7200, losses: 2, srp_filed: 1, aar_link: null } })
    await t.fw.poll()
    assert.equal(t.snapshots.at(-1).view, 'after')
    t.fw.done()
    assert.equal(t.snapshots.at(-1).view, 'list')
})

test('a fleet opened from the list that the current window already covers costs no extra call', async () => {
    const t = setup({ current: payload({ id: 7 }) })
    await t.fw.open(7)
    assert.deepEqual(t.calls, ['current'])
})

test('a recent loss shows once', async () => {
    const loss = { killmail_id: 77, killmail_time: '2026-10-16T20:00:00Z', ship_type_id: 33157, ship_name: 'Hurricane Fleet Issue', isk_value: 168e6, solar_system_name: 'Amamake', srp_filed: false }
    const t = setup({ current: payload({ loss }) })
    await t.fw.poll()
    assert.equal(t.snapshots.at(-1).view, 'loss')

    t.fw.file_srp()
    assert.deepEqual(t.copied, ['https://zkillboard.com/kill/77/'])
    assert.deepEqual(t.opened_urls, ['https://web.example/ships/srp/killmails/'])

    t.fw.dismiss_loss()
    assert.equal(t.snapshots.at(-1).view, 'fleet')
    await t.fw.poll()
    assert.equal(t.snapshots.at(-1).view, 'fleet')
})

test('jumps come from the client in front when it is the pilot in fleet, else from the fleet poll', async () => {
    const t = setup({ current: payload() })
    await t.fw.poll()
    assert.deepEqual(t.routes.asked, [[30002053, 30002537]])   // backend system id -> FC system

    t.fw.set_front({ name: 'Kesra Lund', system: 'Eszur', id: 1001 })
    assert.deepEqual(t.routes.asked.at(-1), ['Eszur', 30002537])

    t.fw.set_front({ name: 'Someone Else', system: 'Rens', id: 9 })
    assert.deepEqual(t.routes.asked.at(-1), [30002053, 30002537])
    assert.equal(t.routes.asked.length, 3)
})

test('the FC view asks for no route', async () => {
    const t = setup({ current: payload({ mode: 'fc' }) })
    await t.fw.poll()
    assert.deepEqual(t.routes.asked, [])
    assert.equal(t.snapshots.at(-1).pilots.length, 1)
})

test('sign-up uses the pilot in front when it is theirs, then re-polls', async () => {
    const t = setup({ current: null, opened: { 9: payload({ id: 9, mode: 'viewer', live: false }) } })
    await t.fw.open(9)
    t.fw.set_front({ name: 'Alt', system: 'Hek', id: 1002 })
    await t.fw.sign_up('f:2')
    assert.ok(t.calls.includes('sign-up:9:1002:f:2'))
    assert.equal(t.calls.at(-1), 'window:9')

    await t.fw.sign_up('f:999')   // not one of this fleet's ships
    assert.ok(!t.calls.some(c => c.endsWith(':f:999')))
})

test('copy fit fetches the composition once and copies its EFT', async () => {
    const t = setup({ current: payload() })
    await t.fw.poll()
    await t.fw.copy_fit('f:2')
    await t.fw.copy_fit('f:2')
    assert.deepEqual(t.copied, ['[Scimitar, Logi]', '[Scimitar, Logi]'])
    assert.equal(t.calls.filter(c => c.startsWith('composition')).length, 1)
    assert.equal(t.snapshots.at(-1).notice, 'Fit copied')
})

test('refresh MOTD is the FC\'s, on a live fleet', async () => {
    const t = setup({ current: payload() })
    await t.fw.poll()
    await t.fw.refresh_motd()
    assert.ok(!t.calls.some(c => c.startsWith('motd')))

    t.api.current = payload({ mode: 'fc' })
    await t.fw.poll()
    await t.fw.refresh_motd()
    assert.ok(t.calls.includes('motd:7'))
})

test('reset forgets the pilot', async () => {
    const t = setup({ current: payload() })
    t.fw.set_active(true)
    await t.clock.advance(0)
    t.fw.reset()
    assert.equal(t.fw.current, null)
    assert.equal(t.clock.pending.size, 0)
    assert.equal(t.fw.view(), 'list')
})
