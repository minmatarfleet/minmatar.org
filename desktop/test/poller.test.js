const { test } = require('node:test')
const assert = require('node:assert/strict')
const { Poller, window_data_wanted, MAX_BACKOFF_MS } = require('../src/main/poller')
const { ApiError } = require('../src/main/api')

const INTERVAL = 60_000

// Fake timers: run what's due when the test says so.
function fake_timers() {
    let now = 1_000_000, next = 1
    const pending = new Map()
    return {
        now: () => now,
        timers: {
            setTimeout: (fn, ms) => { const id = next++; pending.set(id, { at: now + ms, fn }); return id },
            clearTimeout: id => pending.delete(id),
        },
        pending,
        due_in() { return pending.size ? Math.min(...[...pending.values()].map(t => t.at - now)) : null },
        async advance(ms) {
            now += ms
            for (const [id, t] of [...pending]) if (t.at <= now) { pending.delete(id); await t.fn() }
        },
    }
}

function setup({ wanted = true, result = true } = {}) {
    const clock = fake_timers()
    const t = { clock, runs: 0, wanted, result, unauthorized: 0 }
    t.poller = new Poller({
        interval_ms: INTERVAL,
        run: async () => {
            t.runs++
            if (t.result instanceof Error) throw t.result
            return t.result
        },
        wanted: () => t.wanted,
        on_unauthorized: () => { t.unauthorized++ },
        now: clock.now,
        timers: clock.timers,
    })
    return t
}

test('fetches nothing while not wanted (window hidden, closed to the tray, or EVE not running)', async () => {
    const t = setup({ wanted: false })
    t.poller.sync()
    await t.clock.advance(10 * INTERVAL)
    assert.equal(t.runs, 0)
    assert.equal(t.clock.pending.size, 0)
})

test('becoming wanted loads at once, then every interval; hiding stops it', async () => {
    const t = setup()
    t.poller.sync()
    await t.clock.advance(0)
    assert.equal(t.runs, 1)
    assert.equal(t.clock.due_in(), INTERVAL)
    await t.clock.advance(INTERVAL)
    assert.equal(t.runs, 2)

    t.wanted = false
    t.poller.sync()
    assert.equal(t.clock.pending.size, 0)
    await t.clock.advance(5 * INTERVAL)
    assert.equal(t.runs, 2)
})

test('shown again: stale data reloads at once, fresh data waits out the interval', async () => {
    const t = setup()
    t.poller.sync()
    await t.clock.advance(0)
    t.wanted = false
    t.poller.sync()
    await t.clock.advance(10_000)
    t.wanted = true
    t.poller.sync()
    assert.equal(t.clock.due_in(), INTERVAL - 10_000)

    t.wanted = false
    t.poller.sync()
    await t.clock.advance(2 * INTERVAL)
    t.wanted = true
    t.poller.sync()
    assert.equal(t.clock.due_in(), 0)
    await t.clock.advance(0)
    assert.equal(t.runs, 2)
})

test('failures back off, doubling up to the cap; a success resets it', async () => {
    const t = setup({ result: false })
    t.poller.sync()
    await t.clock.advance(0)
    assert.equal(t.clock.due_in(), INTERVAL * 2)
    await t.clock.advance(t.clock.due_in())
    assert.equal(t.clock.due_in(), INTERVAL * 4)
    for (let i = 0; i < 5; i++) await t.clock.advance(t.clock.due_in())
    assert.equal(t.clock.due_in(), MAX_BACKOFF_MS)

    t.result = new Error('offline')   // a throw counts as a failure too
    await t.clock.advance(t.clock.due_in())
    assert.equal(t.clock.due_in(), MAX_BACKOFF_MS)

    t.result = true
    await t.clock.advance(t.clock.due_in())
    assert.equal(t.clock.due_in(), INTERVAL)
})

test('a forced poll runs while not wanted, once, without starting a schedule', async () => {
    const t = setup({ wanted: false })
    t.poller.sync()
    await t.poller.poll()
    assert.equal(t.runs, 1)
    assert.equal(t.clock.pending.size, 0)
})

test('a poll already in flight is joined, not started twice', async () => {
    const t = setup()
    let release
    t.poller.run = () => { t.runs++; return new Promise(resolve => { release = resolve }) }
    const a = t.poller.poll()
    const b = t.poller.poll()
    assert.equal(a, b)
    release(true)
    await a
    assert.equal(t.runs, 1)
})

test('a 401 hands over to sign-out once and stops polling', async () => {
    const t = setup({ result: new ApiError(401, 'expired') })
    t.poller.sync()
    await t.clock.advance(0)
    assert.equal(t.unauthorized, 1)
    assert.equal(t.clock.pending.size, 0)
    await t.clock.advance(10 * INTERVAL)
    assert.equal(t.runs, 1)
})

test('sign-out (reset) mid-poll: the old run schedules nothing, the next pilot loads at once', async () => {
    const t = setup()
    let release
    t.poller.run = () => { t.runs++; return new Promise(resolve => { release = resolve }) }
    t.poller.sync()
    const run = t.poller.poll()   // the scheduled poll, run now (advance() would wait for it)
    t.poller.reset()
    release(false)
    await run
    assert.equal(t.clock.pending.size, 0)
    assert.equal(t.poller.failures, 0)
    t.poller.sync()
    assert.equal(t.clock.due_in(), 0)
})

test('a window\'s data is wanted only while the window can show', () => {
    const up = { signed_in: true, open: true, hidden: false, helper: { supported: true, failed: false, eve_running: true } }
    assert.equal(window_data_wanted(up), true)
    assert.equal(window_data_wanted({ ...up, signed_in: false }), false)
    assert.equal(window_data_wanted({ ...up, open: false }), false)              // disabled in Settings
    assert.equal(window_data_wanted({ ...up, hidden: true }), false)             // closed or minimised to the tray
    assert.equal(window_data_wanted({ ...up, helper: { supported: true, failed: false, eve_running: false } }), false)   // EVE closed
    assert.equal(window_data_wanted({ ...up, helper: { supported: true, failed: false, eve_running: false, ready: false } }), false)   // helper starting
    assert.equal(window_data_wanted({ ...up, helper: { supported: false } }), true)   // not Windows: windows float, nothing to wait for
    assert.equal(window_data_wanted({ ...up, helper: { supported: true, failed: true } }), true)   // PowerShell blocked
    assert.equal(window_data_wanted({ ...up, helper: null }), true)
})
