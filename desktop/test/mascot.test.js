const { test } = require('node:test')
const assert = require('node:assert/strict')
const { badge_rect, mascot_rect } = require('../src/main/mascot')
const { mascot_should_show } = require('../src/main/overlay_rules')
const { OVERLAY_WINDOWS, window_def } = require('../src/main/windows')

const CLIENT = { x: 0, y: 0, w: 3440, h: 1440 }

test('badge matches the measured position on a 3440x1440 client at UI scale 1', () => {
    assert.deepEqual(badge_rect(CLIENT), { x: 3392, y: 1392, width: 32, height: 32 })
})

test('Sneak sits centred on top of the badge, following offset, scale and client position', () => {
    const m = mascot_rect(CLIENT)
    assert.equal(m.x + m.width / 2, 3392 + 16)
    assert.equal(m.y + m.height, 1392 + 1)            // ducks one unit behind the badge's top edge
    const moved = badge_rect({ x: 100, y: 50, w: 1920, h: 1080 }, { offset: [40, 120], scale: 1.25 })
    assert.deepEqual(moved, { x: 100 + 1920 - 50 - 40, y: 50 + 1080 - 150 - 40, width: 40, height: 40 })
    assert.equal(mascot_rect(CLIENT, { scale: 1.5 }).width, 60)
})

const fg = extra => ({ hwnd: '9', pid: 5, proc: 'chrome', cls: 'x', client: false, ...extra })
const base = { helper_ready: true, own_pids: new Set([1]), active_client: { hwnd: '7', title: 'EVE - Kaleb Snowden', min: false } }

test('Sneak shows over a logged-in client, never over other apps, character select, or without a client', () => {
    assert.equal(mascot_should_show({ ...base, foreground: fg({ client: true, title: 'EVE - Kaleb Snowden' }) }), true)
    assert.equal(mascot_should_show({ ...base, foreground: fg({ client: true, title: 'EVE' }) }), false)
    assert.equal(mascot_should_show({ ...base, foreground: fg() }), false)
    assert.equal(mascot_should_show({ ...base, foreground: fg({ pid: 1 }) }), true)                  // Settings open
    assert.equal(mascot_should_show({ ...base, foreground: fg({ proc: 'ScreenClippingHost' }) }), null)
    assert.equal(mascot_should_show({ ...base, active_client: null, foreground: fg({ pid: 1 }) }), false)
    assert.equal(mascot_should_show({ ...base, active_client: { hwnd: '7', min: true }, foreground: fg({ pid: 1 }) }), false)
    assert.equal(mascot_should_show({ ...base, helper_ready: false, foreground: fg({ pid: 1 }) }), false)
})

test('with "Stay with EVE" Sneak stays on his client under other apps', () => {
    assert.equal(mascot_should_show({ ...base, stay_with_eve: true, foreground: fg() }), true)
    assert.equal(mascot_should_show({ ...base, stay_with_eve: true, active_client: { hwnd: '7', title: 'EVE', min: false }, foreground: fg() }), false)
    assert.equal(mascot_should_show({ ...base, stay_with_eve: true, active_client: { hwnd: '7', title: 'EVE - Kaleb Snowden', min: true }, foreground: fg() }), false)
})

test('window registry entries are complete and unique', () => {
    const ids = OVERLAY_WINDOWS.map(w => w.id)
    assert.equal(new Set(ids).size, ids.length)
    for (const w of OVERLAY_WINDOWS) {
        for (const key of ['title', 'description', 'page', 'size', 'min_size']) assert.ok(w[key], `${w.id}.${key}`)
        assert.equal(typeof w.default_enabled, 'boolean')
    }
    assert.equal(window_def('fleets').page, 'fleets.html')
    assert.equal(window_def('nope'), null)
})
