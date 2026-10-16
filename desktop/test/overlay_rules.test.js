const { test } = require('node:test')
const assert = require('node:assert/strict')
const { overlay_should_show, hide_instantly } = require('../src/main/overlay_rules')

const base = { helper_ready: true, eve_running: true, own_pids: new Set([42]), only_over_eve: true }
const fg = (extra) => ({ hwnd: '100', pid: 7, proc: 'chrome', cls: 'Chrome_WidgetWin_1', client: false, ...extra })

test('shows over an EVE client or this app, hides over other apps', () => {
    assert.equal(overlay_should_show({ ...base, foreground: fg({ client: true, proc: 'exefile', title: 'EVE - Kaleb Snowden' }) }), true)
    assert.equal(overlay_should_show({ ...base, foreground: fg({ pid: 42 }) }), true)
    assert.equal(overlay_should_show({ ...base, foreground: fg() }), false)
})

test('screenshot tools keep the overlay where it is (so it is in the capture)', () => {
    for (const proc of ['ScreenClippingHost', 'SnippingTool', 'ShareX', 'Greenshot', 'Lightshot']) {
        assert.equal(overlay_should_show({ ...base, foreground: fg({ proc }) }), null, proc)
    }
})

test('taskbar / Alt+Tab / Start keep it; the desktop and File Explorer do not', () => {
    assert.equal(overlay_should_show({ ...base, foreground: fg({ proc: 'explorer', cls: 'Shell_TrayWnd' }) }), null)
    assert.equal(overlay_should_show({ ...base, foreground: fg({ proc: 'explorer', cls: 'XamlExplorerHostIslandWindow' }) }), null)
    assert.equal(overlay_should_show({ ...base, foreground: fg({ proc: 'StartMenuExperienceHost' }) }), null)
    assert.equal(overlay_should_show({ ...base, foreground: fg({ proc: 'explorer', cls: 'CabinetWClass' }) }), false)
})

test('mid-switch (no foreground window) keeps the current state', () => {
    assert.equal(overlay_should_show({ ...base, foreground: fg({ hwnd: '0' }) }), null)
})

test('always visible when "Only over EVE" is off, EVE is not running, or the helper is unavailable', () => {
    assert.equal(overlay_should_show({ ...base, only_over_eve: false, foreground: fg() }), true)
    assert.equal(overlay_should_show({ ...base, eve_running: false, foreground: fg() }), true)
    assert.equal(overlay_should_show({ ...base, helper_ready: false, foreground: fg() }), true)
})

test('a client still at character select does not get the overlay', () => {
    assert.equal(overlay_should_show({ ...base, foreground: fg({ client: true, proc: 'exefile', title: 'EVE' }) }), false)
    assert.equal(overlay_should_show({ ...base, foreground: fg({ client: true, proc: 'exefile', title: 'EVE - ' }) }), false)
})

test('switching to a client at character select hides instantly; other apps fade', () => {
    assert.equal(hide_instantly(fg({ client: true, proc: 'exefile', title: 'EVE' })), true)
    assert.equal(hide_instantly(fg({ client: true, proc: 'exefile', title: 'EVE - Kaleb Snowden' })), false)
    assert.equal(hide_instantly(fg()), false)
})
