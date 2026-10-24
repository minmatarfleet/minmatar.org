const { test } = require('node:test')
const assert = require('node:assert/strict')
const { update_prompt, show_update, wire_update } = require('../src/renderer/eve_window')

test('every overlay offers the same update prompt', () => {
    assert.deepEqual(update_prompt({ status: 'ready', version: '0.11.0' }), {
        label: 'Restart to update', title: 'v0.11.0 is downloaded. Restart the app to install it', command: 'update:install',
    })
    // Portable builds can't update themselves: link to the release.
    assert.deepEqual(update_prompt({ status: 'available', version: '0.11.0', portable: true }), {
        label: 'v0.11.0 available', title: 'Open the release page to download it', command: 'update:download',
    })
    for (const status of ['idle', 'checking', 'downloading', undefined]) assert.equal(update_prompt({ status, version: '0.11.0' }), null)
    assert.equal(update_prompt(undefined), null)
})

test('the footer button shows the prompt and sends its command', () => {
    const listeners = []
    const button = { hidden: true, textContent: '', title: '', dataset: {}, addEventListener: (type, fn) => listeners.push(fn) }
    const sent = []
    wire_update(button, command => sent.push(command))
    listeners[0]()
    assert.deepEqual(sent, [], 'nothing to send before there is an update')
    show_update(button, { status: 'available', version: '0.11.0' })
    assert.equal(button.hidden, false)
    assert.equal(button.textContent, 'v0.11.0 available')
    listeners[0]()
    show_update(button, { status: 'ready', version: '0.11.0' })
    listeners[0]()
    assert.deepEqual(sent, ['update:download', 'update:install'])
    show_update(button, { status: 'idle' })
    assert.equal(button.hidden, true)
})
