const { test, afterEach } = require('node:test')
const assert = require('node:assert/strict')
const { Settings } = require('../src/main/settings')

const DEFAULTS = { overlay: true, only_over_eve: true, show_sneak: true }
const offline = () => Object.assign(new Error('fetch failed'), { status: undefined })
const http = status => Object.assign(new Error(`HTTP ${status}`), { status })
const tick = (ms = 5) => new Promise(resolve => setTimeout(resolve, ms))

// A stand-in for the account API: a values map with PATCH-merge semantics, switchable up/down.
function fake_remote(initial = {}) {
    const remote = { values: { ...initial }, up: true, loads: 0, saves: [] }
    remote.load = async () => {
        remote.loads++
        if (!remote.up) throw offline()
        return { values: { ...remote.values } }
    }
    remote.save = async values => {
        if (remote.fail_with) throw remote.fail_with
        if (!remote.up) throw offline()
        remote.saves.push(values)
        for (const [k, v] of Object.entries(values)) v === null ? delete remote.values[k] : (remote.values[k] = v)
        return { values: { ...remote.values } }
    }
    return remote
}

// Stop every store's retry timers after each test, so a failing assertion can't leave them spinning.
const made = []
afterEach(() => { for (const settings of made.splice(0)) settings.stop() })

function make(remote, options = {}) {
    const settings = new Settings({ defaults: DEFAULTS, session_keys: ['overlay'], remote, save_delay_ms: 1, retry_ms: [5], ...options })
    settings.on('error', () => {})
    made.push(settings)
    return settings
}

test('loads the account copy over the defaults and reports what changed', async () => {
    const remote = fake_remote({ show_sneak: false, 'window.fleets': { bounds: { x: 1, y: 2, width: 3, height: 4 } } })
    const settings = make(remote)
    const changes = []
    settings.on('change', keys => changes.push(keys))
    assert.equal(await settings.load(), true)
    assert.equal(settings.get('show_sneak'), false)
    assert.deepEqual(settings.get('window.fleets'), { bounds: { x: 1, y: 2, width: 3, height: 4 } })
    assert.deepEqual(changes, [['show_sneak', 'window.fleets']])
    assert.equal(settings.status, 'synced')
})

test('sends only changed keys, debounced into one request', async () => {
    const remote = fake_remote({ only_over_eve: false })
    const settings = make(remote)
    await settings.load()
    settings.set('show_sneak', false)
    settings.set('window.fleets', { enabled: true })
    settings.set('window.fleets', { enabled: false })
    settings.set('show_sneak', false)   // unchanged: no extra key, no extra request
    await tick()
    assert.deepEqual(remote.saves, [{ show_sneak: false, 'window.fleets': { enabled: false } }])
    assert.equal(remote.values.only_over_eve, false)   // untouched key survives the merge
    assert.equal(settings.has_pending(), false)
})

test('session keys never reach the API', async () => {
    const remote = fake_remote({ overlay: false })
    const settings = make(remote)
    await settings.load()
    assert.equal(settings.get('overlay'), true)   // the account can't unpin a new launch either
    settings.set('overlay', false)
    await tick()
    assert.deepEqual(remote.saves, [])
    assert.equal(settings.has_pending(), false)
})

test('API down at launch: runs on defaults, keeps changes, and catches up when it is back', async () => {
    const remote = fake_remote({ show_sneak: false, only_over_eve: false })
    remote.up = false
    const settings = make(remote)
    const changes = []
    settings.on('change', keys => changes.push(keys))

    assert.equal(await settings.load(), false)
    assert.equal(settings.get('show_sneak'), true)
    assert.equal(settings.status, 'offline')

    settings.set('only_over_eve', true)          // pilot changes something while offline
    await tick(20)
    assert.equal(settings.has_pending(), true)    // still held, retrying

    remote.up = true
    await tick(30)
    assert.equal(settings.loaded, true)
    assert.equal(settings.get('show_sneak'), false)       // account copy applied...
    assert.equal(settings.get('only_over_eve'), true)     // ...but the offline change wins
    assert.equal(remote.values.only_over_eve, true)
    assert.deepEqual(changes, [['show_sneak']])
    assert.equal(settings.has_pending(), false)
    assert.equal(settings.status, 'synced')
})

test('a key changed while its save is in flight is sent again', async () => {
    const remote = fake_remote()
    let release
    const real_save = remote.save
    remote.save = values => new Promise(resolve => { release = () => resolve(real_save(values)) })
    const settings = make(remote)
    await settings.load()
    settings.set('window.fleets', { bounds: { x: 1 } })
    await tick()
    settings.set('window.fleets', { bounds: { x: 2 } })
    remote.save = real_save
    release()
    await tick(20)
    assert.deepEqual(remote.values['window.fleets'], { bounds: { x: 2 } })
    assert.equal(settings.has_pending(), false)
})

test('rejected values (400) and signed-out saves (401) are dropped, not retried forever', async () => {
    for (const status of [400, 401]) {
        const remote = fake_remote()
        const settings = make(remote)
        await settings.load()
        remote.fail_with = http(status)
        settings.set('show_sneak', false)
        assert.equal(await settings.flush(), true)
        assert.equal(settings.has_pending(), false)
    }
})

test('reset (sign-out) forgets the old pilot, and a late reply for them is ignored', async () => {
    const remote = fake_remote({ show_sneak: false })
    let release
    remote.load = () => new Promise(resolve => { release = () => resolve({ values: { show_sneak: false } }) })
    const settings = make(remote)
    const pending_load = settings.load()
    settings.set('only_over_eve', false)
    settings.reset()
    release()
    assert.equal(await pending_load, false)
    assert.equal(settings.get('show_sneak'), true)
    assert.equal(settings.get('only_over_eve'), true)
    assert.equal(settings.has_pending(), false)
})

test('flush sends pending changes immediately (quit)', async () => {
    const remote = fake_remote()
    const settings = make(remote, { save_delay_ms: 60_000 })
    await settings.load()
    settings.set('show_sneak', false)
    assert.equal(await settings.flush(), true)
    assert.deepEqual(remote.saves, [{ show_sneak: false }])
})
