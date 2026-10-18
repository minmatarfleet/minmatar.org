// The window -> main command list lives in three places that must agree: src/main/ipc_commands.js,
// preload.js's allowlist (a sandboxed preload can't require it) and main.js's handlers. A command missing
// from one of them is silently dropped or dead, so these tests compare them.
const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('fs')
const path = require('path')
const vm = require('vm')
const { COMMANDS, id_of, fleet_key, fleet_ship, intel_range, window_toggle } = require('../src/main/ipc_commands')

const SRC = path.join(__dirname, '..', 'src')

// Runs preload.js with a stand-in 'electron' and returns what it exposes plus what it forwarded.
function load_preload() {
    const exposed = {}
    const forwarded = []
    const electron = {
        contextBridge: { exposeInMainWorld: (name, api) => { exposed[name] = api } },
        ipcRenderer: { send: (...args) => forwarded.push(args), on: () => {} },
    }
    const context = vm.createContext({ require: name => { assert.equal(name, 'electron'); return electron } })
    vm.runInContext(fs.readFileSync(path.join(SRC, 'preload', 'preload.js'), 'utf8'), context)
    return { bridge: exposed.minmatar, forwarded, commands: vm.runInContext('COMMANDS', context) }
}

// Loads main.js against a stand-in 'electron' (the app never gets ready) and lists its IPC handlers.
function main_handlers() {
    const channels = []
    const noop = () => {}
    const electron = {
        app: {
            requestSingleInstanceLock: () => true, exit: noop, on: noop, quit: noop, getVersion: () => '0.0.0',
            whenReady: () => new Promise(noop),
        },
        ipcMain: { on: channel => channels.push(channel) },
        BrowserWindow: {}, shell: {}, safeStorage: {}, screen: {}, Tray: function () {}, Menu: {}, nativeImage: {}, clipboard: {}, Notification: {},
    }
    const id = require.resolve('electron')
    const saved = require.cache[id]
    require.cache[id] = { id, filename: id, loaded: true, exports: electron }
    const main = require.resolve('../src/main/main')
    try {
        delete require.cache[main]
        require(main)
    } finally {
        if (saved) require.cache[id] = saved
        else delete require.cache[id]
        delete require.cache[main]
    }
    return channels
}

const sorted = list => [...list].sort()

test('preload allows exactly the commands in ipc_commands.js', () => {
    const { commands } = load_preload()
    assert.deepEqual(sorted(commands), sorted(COMMANDS))
    assert.equal(new Set(COMMANDS).size, COMMANDS.length, 'no command listed twice')
})

test('preload forwards listed commands and drops anything else', () => {
    const { bridge, forwarded } = load_preload()
    bridge.send('fleet:open', 7)
    bridge.send('fleets:open', 7)        // the old name: gone
    bridge.send('shell:open', 'https://evil.example')
    assert.deepEqual(forwarded, [['fleet:open', 7]])
})

test('main.js handles every command once, and only those', () => {
    const channels = main_handlers()
    assert.deepEqual(sorted(channels), sorted(COMMANDS))
})

test('every command a window sends is allowed, and every allowed command has a sender', () => {
    const dir = path.join(SRC, 'renderer')
    const sources = fs.readdirSync(dir).filter(f => /\.(js|html)$/.test(f)).map(f => fs.readFileSync(path.join(dir, f), 'utf8')).join('\n')
    const sent = new Set([...sources.matchAll(/['"`]([a-z]+:[a-z-]+)['"`]/g)].map(m => m[1]))
    for (const command of sent) assert.ok(COMMANDS.includes(command), `${command} is sent by a window but not allowed`)
    for (const command of COMMANDS) assert.ok(sent.has(command), `${command} is allowed but no window sends it`)
})

test('ids, ship keys and other values from the windows', () => {
    assert.equal(id_of(7), 7)
    for (const bad of [0, -1, 1.5, '7', null, undefined, NaN, 2 ** 60, {}]) assert.equal(id_of(bad), null, String(bad))
    assert.equal(fleet_key('f:12'), 'f:12')
    assert.equal(fleet_key('m:3'), 'm:3')
    for (const bad of ['x:1', 'f:', 'f:1 ', 'f:1;m:2', 12, null]) assert.equal(fleet_key(bad), null, String(bad))
    assert.deepEqual(fleet_ship({ fleet_id: 7, key: 'f:1', extra: 'dropped' }), { fleet_id: 7, key: 'f:1' })
    assert.equal(fleet_ship({ fleet_id: '7', key: 'f:1' }), null)
    assert.equal(fleet_ship({ fleet_id: 7, key: 'f:1"' }), null)
    assert.equal(fleet_ship(null), null)
    assert.equal(intel_range(5), 5)
    assert.equal(intel_range(null), null)
    for (const bad of [undefined, 2.5, '5', {}]) assert.equal(intel_range(bad), undefined, String(bad))
    assert.deepEqual(window_toggle({ id: 'intel', enabled: true }), { id: 'intel', enabled: true })
    for (const bad of [null, { id: 'intel', enabled: 'yes' }, { id: 3, enabled: true }, {}]) assert.equal(window_toggle(bad), null)
})
