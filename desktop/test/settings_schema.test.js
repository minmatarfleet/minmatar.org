// Account settings are shared by every installed version of the app, so reads must accept exactly what
// any version writes, fall back to defaults on anything else, and never drop what a newer version added.
const { test } = require('node:test')
const assert = require('node:assert/strict')
const { TOGGLES, read_toggle, window_key, stored_window, read_bounds, read_range, read_window, read_reminders } = require('../src/main/settings_schema')
const { OVERLAY_WINDOWS, window_def } = require('../src/main/windows')

test('toggles: booleans as stored, anything else is the default', () => {
    assert.deepEqual(TOGGLES, { locked: true, show_sneak: true, fade_on_right_click: true })
    assert.equal(read_toggle('show_sneak', false), false)
    assert.equal(read_toggle('show_sneak', true), true)
    for (const other of [undefined, null, 0, 'false', {}, []]) assert.equal(read_toggle('show_sneak', other), true, String(other))
})

test('window.<id>: enabled, bounds and range, each falling back on its own', () => {
    const intel = window_def('intel')
    const fleets = window_def('fleets')
    assert.equal(window_key('intel'), 'window.intel')
    assert.deepEqual(read_window(undefined, fleets), { enabled: true, bounds: null, range: undefined })
    assert.deepEqual(read_window(undefined, intel), { enabled: false, bounds: null, range: undefined })
    const saved = { enabled: true, bounds: { x: -1200, y: 80, width: 420, height: 460 }, range: 10 }
    assert.deepEqual(read_window(saved, intel), saved)
    assert.deepEqual(read_window({ enabled: 'yes', bounds: { x: 1, y: 2 }, range: '5' }, intel), { enabled: false, bounds: null, range: undefined })
    assert.deepEqual(read_window('garbage', fleets), { enabled: true, bounds: null, range: undefined })
    for (const def of OVERLAY_WINDOWS) assert.equal(typeof read_window(null, def).enabled, 'boolean')
})

test('bounds need four finite numbers', () => {
    assert.deepEqual(read_bounds({ x: 0, y: 0, width: 380, height: 520, display: 2 }), { x: 0, y: 0, width: 380, height: 520 })
    assert.equal(read_bounds({ x: 0, y: 0, width: 380 }), null)
    assert.equal(read_bounds({ x: 0, y: 0, width: 380, height: NaN }), null)
    assert.equal(read_bounds({ x: '0', y: 0, width: 380, height: 520 }), null)
    assert.equal(read_bounds(null), null)
})

test('intel range: whole jumps or null (any distance); anything else is unset', () => {
    assert.equal(read_range(5), 5)
    assert.equal(read_range(0), 0)
    assert.equal(read_range(-3), 0)
    assert.equal(read_range(null), null)
    for (const other of [undefined, 2.5, '5', true]) assert.equal(read_range(other), undefined, String(other))
})

test('a save keeps fields and keys this version does not know', () => {
    // A newer version added window.fleets.monitor; an older one moves the window.
    const stored = { enabled: true, bounds: { x: 0, y: 0, width: 380, height: 520 }, monitor: 'DISPLAY2' }
    const saved = { ...stored_window(stored), bounds: { x: 10, y: 10, width: 380, height: 520 } }
    assert.equal(saved.monitor, 'DISPLAY2')
    assert.equal(saved.enabled, true)
    // Garbage under the key is replaced, not spread character by character.
    assert.deepEqual(stored_window('abc'), {})
    assert.deepEqual(stored_window(null), {})
    assert.deepEqual(stored_window([1]), {})
})

test('reading never changes the stored value', () => {
    const stored = { enabled: 'maybe', bounds: { x: 'a' }, range: 2.5, future: { a: 1 } }
    const copy = JSON.parse(JSON.stringify(stored))
    read_window(stored, window_def('intel'))
    assert.deepEqual(stored, copy)
})

test('reminders: entries with a fleet id', () => {
    const list = [{ id: 7, at: '2026-10-17T19:00:00Z', title: 'Fleet', where: 'Amamake' }, { id: '8' }, null, 'x', { at: 'no id' }, { id: 9, extra: true }]
    assert.deepEqual(read_reminders(list).map(r => r.id), [7, 9])
    assert.deepEqual(read_reminders({ 7: {} }), [])
    assert.deepEqual(read_reminders(undefined), [])
})
