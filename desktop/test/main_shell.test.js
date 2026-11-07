// Boots main.js against a stand-in Electron and a stand-in EVE helper, signed in from a stored session,
// and drives what has no page of its own: the tray menu, About, Sneak and windows closed to the tray.
const { test, before } = require('node:test')
const assert = require('node:assert/strict')
const { EventEmitter } = require('events')
const fs = require('fs')
const os = require('os')
const path = require('path')

// main.js starts intervals (reminders, polling) that would keep this test process alive; the test's own
// waits keep a real timer.
const wait = global.setTimeout
for (const name of ['setTimeout', 'setInterval']) {
    const original = global[name]
    global[name] = (...args) => { const handle = original(...args); if (handle && handle.unref) handle.unref(); return handle }
}

const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'mf-main-'))
const handlers = new Map()
const dialogs = []
const opened_urls = []
let tray = null
const windows = []

class FakeWebContents extends EventEmitter {
    constructor(owner) { super(); this.owner = owner; this.sent = [] }
    send(channel, value) { this.sent.push([channel, value]) }
    isLoading() { return false }
    setWindowOpenHandler() {}
}

class FakeWindow extends EventEmitter {
    constructor(options) {
        super()
        this.options = options
        this.bounds = { x: options.x || 0, y: options.y || 0, width: options.width || 100, height: options.height || 100 }
        this.visible = false
        this.destroyed = false
        this.focusable = options.focusable !== false
        this.webContents = new FakeWebContents(this)
        windows.push(this)
    }
    static fromWebContents(contents) { return contents.owner }
    loadFile(file) { this.page = path.basename(file); setImmediate(() => { this.emit('ready-to-show'); this.webContents.emit('did-finish-load') }) }
    show() { this.visible = true }
    showInactive() { this.visible = true }
    hide() { this.visible = false }
    isVisible() { return this.visible }
    isDestroyed() { return this.destroyed }
    getBounds() { return { ...this.bounds } }
    setBounds(bounds) { this.bounds = { ...this.bounds, ...bounds } }
    setIgnoreMouseEvents() {}
    setAlwaysOnTop() {}
    moveTop() {}
    minimize() {}
    focus() {}
    isFocusable() { return this.focusable }
    setFocusable(on) { this.focusable = on }
    getNativeWindowHandle() { return Buffer.alloc(8) }
    close() {
        const event = { prevented: false, preventDefault() { this.prevented = true } }
        this.emit('close', event)
        if (!event.prevented) this.destroy()
    }
    destroy() { if (this.destroyed) return; this.destroyed = true; this.visible = false; this.emit('closed') }
}

const app = new EventEmitter()
Object.assign(app, {
    requestSingleInstanceLock: () => true, exit() {}, quit() {}, getVersion: () => '9.9.9', isPackaged: false,
    whenReady: () => Promise.resolve(), setAppUserModelId() {},
    getPath: name => path.join(tmp, name), getAppMetrics: () => [{ pid: process.pid }],
})

const display = { workArea: { x: 0, y: 0, width: 1920, height: 1040 } }
const electron = {
    app,
    BrowserWindow: FakeWindow,
    ipcMain: { on: (channel, fn) => handlers.set(channel, fn) },
    shell: { openExternal: url => opened_urls.push(url) },
    safeStorage: { isEncryptionAvailable: () => true, encryptString: s => Buffer.from(s), decryptString: b => b.toString() },
    screen: {
        getPrimaryDisplay: () => display, getAllDisplays: () => [display], getDisplayNearestPoint: () => display,
        getCursorScreenPoint: () => ({ x: 0, y: 0 }), screenToDipRect: (w, r) => r, dipToScreenRect: (w, r) => r,
    },
    Tray: class extends EventEmitter {
        constructor() { super(); tray = this }
        setToolTip(text) { this.tooltip = text }
        setContextMenu(menu) { this.menu = menu }
    },
    Menu: { buildFromTemplate: template => template },
    nativeImage: { createFromPath: () => ({}) },
    clipboard: { readText: () => '', writeText() {} },
    Notification: { isSupported: () => false },
    dialog: { showMessageBox: options => { dialogs.push(options); return Promise.resolve({ response: 0 }) } },
}

// The EVE helper: ready, with one logged-in client in front.
class FakeEveClients extends EventEmitter {
    constructor() {
        super()
        this.supported = true
        this.ready = false
        this.failed = false
        this.clients = [{ hwnd: '11', title: 'EVE - Kesra Lund', x: 0, y: 0, w: 1920, h: 1080, min: false }]
        this.foreground = { client: true, hwnd: '11', pid: 4242, title: 'EVE - Kesra Lund', proc: 'exefile', cls: '' }
    }
    get eve_running() { return this.clients.length > 0 }
    start() { setImmediate(() => { this.ready = true; this.emit('ready') }) }
    stop() {}
    apply_glass() {}
    watch_buttons() {}
    stack() {}
}

// The API: who you are, your saved settings, and empty lists for the rest.
global.fetch = async url => {
    const path_only = new URL(url).pathname
    const body = path_only === '/api/users/me'
        ? { user_id: 7, username: 'kesra', eve_character_profile: { character_id: 90000001, character_name: 'Kesra Lund' }, discord_user_profile: null }
        : path_only === '/api/users/me/desktop-settings' ? { values: {} }
        : path_only.startsWith('/api/fleets/v3') ? []
        : {}
    return { ok: true, status: 200, headers: { get: () => null }, json: async () => body }
}

const flush = () => new Promise(resolve => wait(resolve, 150))
const by_page = page => windows.filter(w => w.page === page && !w.destroyed)
const item = (label, menu = tray.menu) => menu.find(i => typeof i.label === 'string' && i.label.startsWith(label))
const send = (channel, win, value) => handlers.get(channel)({ sender: win.webContents }, value)
const last_state = win => win.webContents.sent.filter(([c]) => c === 'state').at(-1)[1]

before(async () => {
    process.argv.push(`--logs=${path.join(tmp, 'logs')}`)
    // A stored session, so start-up signs straight in.
    fs.mkdirSync(path.join(tmp, 'userData'), { recursive: true })
    fs.writeFileSync(path.join(tmp, 'userData', 'session.bin'), 'header.e30.sig')
    const inject = (id, exports) => { require.cache[id] = { id, filename: id, loaded: true, exports } }
    inject(require.resolve('electron'), electron)
    inject(require.resolve('../src/main/eve_clients'), { EveClients: FakeEveClients })
    require('../src/main/main')
    await flush()
})

test('signed in from the stored session: the Fleets window opens and the tray names the pilot', () => {
    assert.equal(by_page('fleets.html').length, 1)
    assert.match(tray.tooltip, /Kesra Lund/)
    assert.equal(item('Sign out').label, 'Sign out (Kesra Lund)')
})

test('tray About shows the version and the CCP notice', async () => {
    item('About').click()
    assert.equal(dialogs.length, 1)
    assert.equal(dialogs[0].message, 'Minmatar Fleet v9.9.9')
    assert.match(dialogs[0].detail, /© CCP hf\. All rights reserved/)
})

test('tray Windows turns windows on and off, like Settings', async () => {
    const submenu = item('Windows').submenu
    assert.deepEqual(submenu.map(i => [i.label, i.checked]), [['Fleets', true], ['Campaigns', false], ['Intel', false]])
    submenu[1].click({ checked: true })
    await flush()
    assert.equal(by_page('campaigns.html').length, 1)
    assert.equal(item('Windows').submenu[1].checked, true)
    item('Windows').submenu[1].click({ checked: false })
    await flush()
    assert.equal(by_page('campaigns.html').length, 0)
})

test('a window closed with × is marked hidden in Settings, and Show brings it back', async () => {
    const fleets = by_page('fleets.html')[0]
    fleets.close()
    await flush()
    assert.equal(fleets.destroyed, false)                     // hidden to the tray, not destroyed
    assert.equal(last_state(fleets).windows.find(w => w.id === 'fleets').hidden, true)
    send('window:set-enabled', fleets, { id: 'fleets', enabled: true })   // Settings' Show button
    await flush()
    assert.equal(fleets.visible, true)
    assert.equal(last_state(fleets).windows.find(w => w.id === 'fleets').hidden, false)
})

test('Sneak opens Settings and a second click on him closes it; the gear only ever opens it', async () => {
    const sneak = by_page('mascot.html')[0]
    assert.ok(sneak, 'Sneak is up on the logged-in client')
    send('settings:open', sneak)
    await flush()
    assert.equal(by_page('settings.html').length, 1)
    send('settings:open', sneak)
    await flush()
    assert.equal(by_page('settings.html').length, 0)

    const fleets = by_page('fleets.html')[0]
    send('settings:open', fleets)
    await flush()
    send('settings:open', fleets)
    await flush()
    assert.equal(by_page('settings.html').length, 1)
})

test('with every window off, Show windows opens Settings instead of doing nothing', async () => {
    by_page('settings.html').forEach(w => w.close())
    item('Windows').submenu[0].click({ checked: false })
    await flush()
    assert.equal(by_page('fleets.html').length, 0)
    item('Show windows').click()
    await flush()
    assert.equal(by_page('settings.html').length, 1)
})
