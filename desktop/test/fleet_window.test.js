const { test } = require('node:test')
const assert = require('node:assert/strict')
const { FleetWindow, POLL_MS, MINE_POLL_MS, MAX_BACKOFF_MS, REMINDERS_KEY } = require('../src/main/fleet_window')
const { ApiError } = require('../src/main/api')

const NOW = Date.parse('2026-10-17T18:00:00Z')
const AMAMAKE = 30002537, HEK = 30002053

// A window payload as GET /api/fleets/window/current returns it (backend fleets/helpers/fleet_window.py).
function payload({ id = 7, mode = 'member', live = true, characters, loss = null, after_action = null, volunteers = {}, feed = [] } = {}) {
    return {
        mode,
        fleet: {
            id, type: 'strategic', type_label: 'Strategic', title: 'Hurricane Fleet', live,
            started_at: '2026-10-17T17:00:00Z', ended_at: live ? null : '2026-10-17T17:50:00Z', start_time: '2026-10-17T17:00:00Z',
            fc_character_id: 5000, fc_name: 'The FC', fc_system_id: AMAMAKE, fc_system_name: 'Amamake',
            location_name: 'Amamake - Freeport', location_system_id: AMAMAKE, location_system_name: 'Amamake', doctrine_name: 'Hurricane Fleet',
        },
        counts: { in_fleet: 24, with_fc: 19, kills: 6, losses: 2, isk_destroyed: 1_420_000_000, isk_lost: 312_000_000 },
        ships: [
            { key: 'f:1', name: 'HFI', ship_type_id: 33157, ship_name: 'Hurricane Fleet Issue', role: 'primary', role_label: 'Mainline', flying: 14, signed_up: 15 },
            { key: 'f:2', name: 'Scimitar', ship_type_id: 11978, ship_name: 'Scimitar', role: 'support', role_label: 'Logi', flying: 2, signed_up: 4 },
        ],
        roles: [{ role: 'logi', covered: true }, { role: 'cyno', covered: false }],
        needs: [],
        pilots: mode === 'fc' ? [{ character_id: 1 }] : [],
        attention: [],
        after_action,
        feed,
        me: {
            character_ids: [1001, 1002],
            characters: characters || (mode === 'member' ? [
                { character_id: 1001, character_name: 'Kesra Lund', ship_type_id: 33157, ship_name: 'Hurricane Fleet Issue', solar_system_id: HEK, solar_system_name: 'Hek', docked: false, doctrine: true, capsule: false },
            ] : []),
            ship_volunteers: volunteers,
            last_loss: loss,
        },
    }
}

// A schedule row as api.js load_upcoming_fleets builds it.
function row(id, { live = false, hours = 24, fc_user_id = 99, status = 'pending' } = {}) {
    return {
        id, type: 'strategic', type_label: 'Strategic', audience: null, description: '', location: 'Amamake',
        start_time: new Date(NOW + hours * 3600_000).toISOString(), status, live, fc_user_id, doctrine: `Fleet ${id}`,
        fc_character_id: 5000, fc_name: 'The FC',
    }
}

const LOSS = { killmail_id: 77, killmail_time: '2026-10-17T17:58:00Z', ship_type_id: 33157, ship_name: 'Hurricane Fleet Issue', isk_value: 168e6, solar_system_name: 'Amamake', srp_filed: false }

// Fake timers: run what's due when the test says so.
function fake_timers() {
    let now = NOW, next = 1
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

function setup({ current = null, windows = {}, mine = { fleets: [], srp_owed: 0, signups: [] }, fail = null, list = [] } = {}) {
    const calls = []
    const clock = fake_timers()
    const copied = [], opened_urls = [], notified = []
    const saved = {}
    const api = {
        current, mine, windows, mine_fail: null,
        async current_fleet_window() {
            calls.push('current')
            if (fail) throw fail
            return { body: { window: api.current }, changed: true }
        },
        async my_fleets() {
            calls.push('mine')
            if (api.mine_fail) throw api.mine_fail
            return { body: api.mine, changed: true }
        },
        async fleet_window(id) {
            calls.push(`window:${id}`)
            if (!(id in api.windows)) throw new ApiError(404, 'gone')
            return { body: api.windows[id], changed: true }
        },
        async fleet_composition(id) {
            calls.push(`composition:${id}`)
            return [{ key: 'f:2', eft_format: '[Scimitar, Logi]' }]
        },
        async set_my_ship(id, character_id, key) { calls.push(`sign-up:${id}:${character_id}:${key}`) },
        async refresh_motd(id) { calls.push(`motd:${id}`) },
        async set_waypoint(character_id, system_id) {
            calls.push(`waypoint:${character_id}:${system_id}`)
            if (api.waypoint_fail) throw api.waypoint_fail
        },
        async preping(id) { calls.push(`preping:${id}`) },
        async start_fleet(id, fc) { calls.push(`start:${id}:${fc}`) },
    }
    const routes = { asked: [], async jumps(origin, destination) { routes.asked.push([origin, destination]); return 3 } }
    const fw = new FleetWindow({
        api, routes, web_url: 'https://web.example',
        clipboard: { writeText: text => copied.push(text) },
        open_external: url => opened_urls.push(url),
        notify: (title, body) => notified.push([title, body]),
        store: { get: key => saved[key], set: (key, value) => { saved[key] = value } },
        now: clock.now, timers: clock.timers,
    })
    fw.set_user(42, 1001)
    if (list.length) fw.set_list(list)
    const snapshots = []
    fw.on('change', s => snapshots.push(s))
    const last = () => snapshots.at(-1)
    return { fw, api, calls, clock, routes, copied, opened_urls, notified, saved, snapshots, last }
}

// ------------------------------------------------------------ the Fleet tab

test('not in a fleet: the Fleet tab shows your next signed-up fleet, else the next one', async () => {
    const t = setup({ list: [row(1, { hours: 2 }), row(2, { hours: 26 })] })
    await t.fw.poll()
    assert.equal(t.last().focus.kind, 'next')
    assert.equal(t.last().next.id, 1)
    assert.equal(t.last().live, null)

    t.api.mine = { fleets: [], srp_owed: 0, signups: [{ fleet_id: 2, character_id: 1001, character_name: 'Kesra Lund', fit_name: '[FL33T] Hurricane Fleet Issue', ship_type_id: 33157 }] }
    await t.clock.advance(MINE_POLL_MS)
    await t.fw.poll()
    assert.equal(t.last().next.id, 2)
    assert.equal(t.last().signups[2].character_name, 'Kesra Lund')
})

test('in a fleet: Fleet shows it and the live strip knows you are behind', async () => {
    const t = setup({ current: payload() })
    await t.fw.poll()
    const s = t.last()
    assert.equal(s.focus.kind, 'current')
    assert.equal(s.focus.fleet.mode, 'member')
    assert.equal(s.focus.fleet.you.character_name, 'Kesra Lund')
    assert.equal(s.live.id, 7)
    assert.equal(s.live.jumps, 3)
})

// The v0.9.1 bug: Back from "Ship lost" dismissed the live fleet and the list had no rows to get back.
test('closing a loss card hides only the card; the fleet never goes away', async () => {
    const t = setup({ current: payload({ loss: LOSS }) })
    await t.fw.poll()
    assert.equal(t.last().focus.kind, 'current')
    assert.equal(t.last().focus.fleet.loss.killmail_id, 77)

    t.fw.dismiss_loss(77)
    assert.equal(t.last().focus.kind, 'current')
    assert.equal(t.last().focus.fleet.loss, null)
    await t.fw.poll()
    assert.equal(t.last().focus.fleet.loss, null)
    assert.equal(t.last().live.id, 7)
    assert.ok(!('dismissed' in t.fw), 'there is no dismissed-fleet state any more')
})

test('File SRP copies the killmail and opens the SRP page, only for losses on screen or in Recent', async () => {
    const t = setup({ current: payload({ loss: LOSS }) })
    await t.fw.poll()
    t.fw.file_srp(77)
    assert.deepEqual(t.copied, ['https://zkillboard.com/kill/77/'])
    assert.deepEqual(t.opened_urls, ['https://web.example/ships/srp/killmails/'])

    t.fw.file_srp(12345)
    assert.equal(t.copied.length, 1)
})

test('the FC keeps the wrap-up until Done, then the tab moves on', async () => {
    const after = { pilots: 30, duration_seconds: 7200, losses: 2, srp_filed: 1, aar_link: null }
    const t = setup({ current: payload({ mode: 'fc', live: false, after_action: after }), list: [row(3)] })
    await t.fw.poll()
    assert.equal(t.last().focus.kind, 'wrapup')
    assert.equal(t.last().live, null)

    t.fw.done()
    assert.equal(t.last().focus.kind, 'next')
    assert.equal(t.last().next.id, 3)
})

test('your sign-up formed without you: the Fleet tab shows its form-up', async () => {
    const t = setup({
        list: [row(9, { live: true, hours: -0.1 })],
        mine: { fleets: [], srp_owed: 0, signups: [{ fleet_id: 9, character_id: 1001, character_name: 'Kesra Lund', fit_name: 'HFI', ship_type_id: 33157 }] },
        windows: { 9: payload({ id: 9, mode: 'viewer', characters: [], volunteers: { 1001: 'f:1' } }) },
    })
    await t.fw.poll()
    assert.deepEqual(t.calls, ['current', 'mine', 'window:9'])
    const s = t.last()
    assert.equal(s.focus.kind, 'formup')
    assert.equal(s.focus.fleet.fleet.id, 9)
    assert.equal(s.focus.fleet.signed_up_key, 'f:1')
})

test('your own fleet within 3 h shows its pre-flight, and Start uses the client in front', async () => {
    const t = setup({
        list: [row(5, { hours: 1, fc_user_id: 42 })],
        windows: { 5: payload({ id: 5, mode: 'fc', live: false }) },
    })
    await t.fw.poll()
    assert.equal(t.last().focus.kind, 'prep')
    assert.equal(t.last().focus.fleet.prepinged, false)

    await t.fw.preping(5)
    assert.ok(t.calls.includes('preping:5'))
    assert.equal(t.last().focus.fleet.prepinged, true)

    t.fw.set_front({ name: 'Alt', system: 'Hek', id: 1002 })
    await t.fw.start(5)
    assert.ok(t.calls.includes('start:5:1002'))
    assert.equal(t.calls.at(-1), 'window:5')   // re-polled
})

test('a fleet you FC tomorrow is just your next fleet', async () => {
    const t = setup({ list: [row(5, { hours: 20, fc_user_id: 42 })] })
    await t.fw.poll()
    assert.equal(t.last().focus.kind, 'next')
    assert.ok(!t.calls.includes('window:5'))
})

// ------------------------------------------------------------ Upcoming

test('only fleets from the schedule open; the fleet you are in costs no extra call', async () => {
    const t = setup({ current: payload({ id: 7 }), list: [row(7, { live: true }), row(9)], windows: { 9: payload({ id: 9, mode: 'viewer', live: false }) } })
    await t.fw.open(1234)
    assert.equal(t.fw.opened, null)

    await t.fw.open(7)
    assert.equal(t.last().opened.is_current, true)
    assert.ok(!t.calls.includes('window:7'))

    await t.fw.open(9)
    assert.equal(t.calls.at(-1), 'window:9')
    assert.equal(t.last().opened.fleet.fleet.id, 9)
    t.fw.close()
    assert.equal(t.last().opened, null)
})

test('sign-up acts as the client in front when it is yours, then re-polls', async () => {
    const t = setup({ list: [row(9)], windows: { 9: payload({ id: 9, mode: 'viewer', live: false }) } })
    await t.fw.open(9)
    t.fw.set_front({ name: 'Alt', system: 'Hek', id: 1002 })
    await t.fw.sign_up(9, 'f:2')
    assert.ok(t.calls.includes('sign-up:9:1002:f:2'))
    assert.equal(t.calls.at(-1), 'window:9')

    await t.fw.sign_up(9, 'f:999')   // not one of this fleet's ships
    await t.fw.sign_up(4321, 'f:2')  // not a fleet on screen
    assert.equal(t.calls.filter(c => c.startsWith('sign-up')).length, 1)
})

test('copy fit fetches the composition once and copies its EFT', async () => {
    const t = setup({ current: payload() })
    await t.fw.poll()
    await t.fw.copy_fit(7, 'f:2')
    await t.fw.copy_fit(7, 'f:2')
    assert.deepEqual(t.copied, ['[Scimitar, Logi]', '[Scimitar, Logi]'])
    assert.equal(t.calls.filter(c => c.startsWith('composition')).length, 1)
    assert.equal(t.last().notice, 'Fit copied')
})

test('reminders are saved on the account and fire once, 15 minutes out', async () => {
    const t = setup({ list: [row(4, { hours: 1 })] })
    t.fw.toggle_reminder(4)
    assert.deepEqual(t.saved[REMINDERS_KEY].map(r => r.id), [4])
    assert.deepEqual(t.last().reminders, [4])

    t.fw.check_reminders()
    assert.equal(t.notified.length, 0)
    await t.clock.advance(46 * 60_000)
    t.fw.check_reminders()
    t.fw.check_reminders()
    assert.equal(t.notified.length, 1)
    assert.match(t.notified[0][0], /Fleet 4 forms in 14 min/)

    await t.clock.advance(30 * 60_000)   // long past: dropped from the account
    t.fw.check_reminders()
    assert.deepEqual(t.saved[REMINDERS_KEY], [])
})

// ------------------------------------------------------------ Set destination

test('set destination only targets systems on screen, as the character in fleet', async () => {
    const t = setup({ current: payload() })
    await t.fw.poll()
    await t.fw.set_destination(30000142)   // Jita: not on screen
    assert.ok(!t.calls.some(c => c.startsWith('waypoint')))

    await t.fw.set_destination(AMAMAKE)
    assert.ok(t.calls.includes(`waypoint:1001:${AMAMAKE}`))
    assert.equal(t.last().notice, 'Destination set: Amamake')
})

test('without the Desktop scopes the API says how to fix it, and that is what shows', async () => {
    const t = setup({ current: payload() })
    await t.fw.poll()
    const err = new ApiError(409, 'POST -> 409')
    err.detail = 'Add the Desktop scopes to Kesra Lund on my.minmatar.org to set destinations'
    t.api.waypoint_fail = err
    await t.fw.set_destination(AMAMAKE)
    assert.match(t.last().notice, /Add the Desktop scopes/)
})

// ------------------------------------------------------------ Recent and polling

test('Recent comes from /window/mine every two minutes, and its failure never fails the poll', async () => {
    const mine = { fleets: [{ fleet_id: 3, title: 'Roam', my_losses: [{ killmail_id: 55, srp_status: 'none' }] }], srp_owed: 1, signups: [] }
    const t = setup({ mine })
    t.fw.set_active(true)
    await t.clock.advance(0)
    assert.equal(t.last().recent.srp_owed, 1)
    await t.clock.advance(POLL_MS)
    assert.deepEqual(t.calls, ['current', 'mine', 'current'])

    t.fw.file_srp(55)   // a loss from Recent
    assert.deepEqual(t.copied, ['https://zkillboard.com/kill/55/'])

    t.api.mine_fail = new ApiError(502, 'down')
    await t.clock.advance(POLL_MS)
    assert.equal(t.last().error, null)
})

test('only publishes when something on screen changed', async () => {
    const t = setup({ current: payload() })
    await t.fw.poll()
    await t.fw.poll()
    await t.fw.poll()
    assert.equal(t.snapshots.length, 2)   // the route lookup lands once with the jump count, then nothing new
})

test('polls every 30 s only while active, and catches up when shown again', async () => {
    const t = setup({ current: payload() })
    t.fw.set_active(true)
    await t.clock.advance(0)
    assert.deepEqual(t.calls, ['current', 'mine'])
    assert.equal(t.clock.due_in(), POLL_MS)

    t.fw.set_active(false)
    assert.equal(t.clock.pending.size, 0)
    await t.clock.advance(10 * POLL_MS)
    assert.equal(t.calls.length, 2)

    t.fw.set_active(true)   // data is stale: poll at once
    await t.clock.advance(0)
    assert.equal(t.calls.filter(c => c === 'current').length, 2)

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
    assert.match(t.last().error, /Retrying/)
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

test('jumps come from the client in front when it is the pilot in fleet, else from the fleet poll', async () => {
    const t = setup({ current: payload() })
    await t.fw.poll()
    assert.deepEqual(t.routes.asked, [[HEK, AMAMAKE]])

    t.fw.set_front({ name: 'Kesra Lund', system: 'Eszur', id: 1001 })
    assert.deepEqual(t.routes.asked.at(-1), ['Eszur', AMAMAKE])

    t.fw.set_front({ name: 'Someone Else', system: 'Rens', id: 9 })
    assert.equal(t.routes.asked.length, 2)   // back to a route it already knows
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
    assert.deepEqual(t.routes.asked, [[HEK, AMAMAKE]])   // the FC view asks for no route
})

test('reset forgets the pilot', async () => {
    const t = setup({ current: payload() })
    t.fw.set_active(true)
    await t.clock.advance(0)
    t.fw.reset()
    assert.equal(t.fw.current, null)
    assert.equal(t.fw.mine, null)
    assert.equal(t.clock.pending.size, 0)
    assert.equal(t.fw.snapshot().focus.kind, 'none')
})
