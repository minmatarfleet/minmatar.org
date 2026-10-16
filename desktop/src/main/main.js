// Minmatar Fleet desktop app: Discord sign-in, EVE-styled overlay windows (see windows.js) pinned as glass
// over the EVE client, a Sneak mascot on EVE's notification badge that opens Settings, and the tray.
const { app, BrowserWindow, ipcMain, shell, safeStorage, screen, Tray, Menu, nativeImage } = require('electron')
const fs = require('fs')
const path = require('path')
const { load_config } = require('./config')
const { start_login, decode_token_payload, TokenStore, LoginCancelled, LoginFailed } = require('./auth')
const { ApiClient, ApiError, load_upcoming_fleets, load_campaign } = require('./api')
const { EveClients } = require('./eve_clients')
const { Settings } = require('./settings')
const { EveWindowSettings, character_id_for_name } = require('./eve_settings')
const { overlay_should_show, mascot_should_show, is_logged_in_client, hide_instantly } = require('./overlay_rules')
const { EveLogEngine } = require('./eve_logs')
const { Updater, RELEASES_URL } = require('./updater')
const { OVERLAY_WINDOWS, window_def } = require('./windows')
const { mascot_rect } = require('./mascot')

const config = load_config()
const DIAG = (process.argv.find(a => a.startsWith('--diag=')) || '').slice(7)
const RENDERER = path.join(__dirname, '..', 'renderer')
const ASSETS = path.join(__dirname, '..', 'assets')
const FADE_MS = 90           // keep in sync with --eve-fade in eve-window.css
const HIDE_DELAY_MS = 60     // focus can pass through a non-EVE window for a moment while switching clients

// Notices required for apps under CCP's Developer License Agreement (docs/desktop/ccp-third-party-guidelines.md rule 17).
const CCP_NOTICE = '© CCP hf. All rights reserved. "EVE", "EVE Online", "CCP", and all related logos and images are ' +
    'trademarks or registered trademarks of CCP hf. This application has been created under the EVE Developer License Agreement. ' +
    'It is a Minmatar Fleet alliance tool and is not affiliated with or endorsed by CCP hf.'

// Settings the Settings window may change (booleans only).
const USER_SETTINGS = ['overlay', 'only_over_eve', 'show_sneak']

function diag(entry) {
    const line = JSON.stringify({ ts: new Date().toISOString(), ...entry })
    console.log(line)
    if (DIAG) try { fs.appendFileSync(DIAG, line + '\n') } catch (e) {}
}

if (!app.requestSingleInstanceLock()) app.exit(0)   // already running: the first instance gets "second-instance" and shows itself

let tokens, settings, api, eve, eve_window, eve_logs, updater, tray
let login_win = null
let settings_win = null
let mascot_win = null
const overlays = new Map()       // window id -> BrowserWindow
const hidden = new Set()         // overlay ids closed/minimised this session (the tray or Settings brings them back)
let active_hwnd = null           // last logged-in EVE client that was in front (Sneak sits on its badge)
let login_flow = null
let refresh_timer = null
let quitting = false
let glass_ready = false

const state = {
    user: null,           // { name, character_id, avatar }
    login: { pending: false, error: null },
    fleets: [],
    loading: false,
    error: null,
    updated_at: null,
    // The Campaigns window's data (null: no live campaign). Only fetched while that window is enabled.
    campaign: null,
    campaign_error: null,
    campaign_updated_at: null,
    // EVE's own settings for the character in front: Settings > Windows transparency (1.0 = default),
    // notification badge offset, UI scale.
    eve_window: { transparency: 1, character_id: null, found: false, badge_offset: null, ui_scale: 1 },
    // Character whose client is in front (or was last) and its solar system, from the log engine.
    location: null,
    update: { status: 'idle', version: null, percent: null, portable: false },
}

// ---------------------------------------------------------------- window plumbing

function base_window(options) {
    const win = new BrowserWindow({
        frame: false,
        transparent: true,
        backgroundColor: '#00000000',
        resizable: false,          // transparent windows can't use native edge-resize on Windows; we use a grip
        maximizable: false,
        fullscreenable: false,
        hasShadow: false,
        show: false,
        icon: path.join(ASSETS, 'icon.png'),
        title: 'Minmatar Fleet',
        webPreferences: {
            preload: path.join(__dirname, '..', 'preload', 'preload.js'),
            contextIsolation: true,
            sandbox: true,
            nodeIntegration: false,
        },
        ...options,
    })
    win.webContents.setWindowOpenHandler(() => ({ action: 'deny' }))
    win.webContents.on('will-navigate', event => event.preventDefault())
    win.webContents.on('did-finish-load', () => {
        if (glass_ready && win !== mascot_win) eve.apply_glass(win)
        // A 'visibility' sent while the page was still loading is lost; re-send the current one.
        win.webContents.send('visibility', win.isVisible() && !fades.has(win))
        push_state()
    })
    return win
}

function all_windows() {
    return [login_win, settings_win, mascot_win, ...overlays.values()].filter(w => w && !w.isDestroyed())
}

function overlay_id_of(win) {
    for (const [id, w] of overlays) if (w === win) return id
    return null
}

// Every show/hide goes through these two so the window fades instead of popping. The page sits at
// opacity 0 whenever the window is hidden, so showing it never flashes the previous frame.
const fades = new Map()   // window -> pending hide timers

function reveal(win, { activate = false } = {}) {
    if (!win || win.isDestroyed()) return
    const pending = fades.get(win)
    if (pending) { clearTimeout(pending.delay); clearTimeout(pending.fade); fades.delete(win) }
    if (!win.isVisible()) activate ? win.show() : win.showInactive()
    win.webContents.send('visibility', true)
}

function conceal(win, { delay = 0, instant = false } = {}) {
    if (!win || win.isDestroyed() || !win.isVisible()) return
    if (instant) {
        const pending = fades.get(win)
        if (pending) { clearTimeout(pending.delay); clearTimeout(pending.fade); fades.delete(win) }
        win.webContents.send('visibility', false)   // so the next show fades in from transparent
        win.hide()
        return
    }
    if (fades.has(win)) return
    const pending = {}
    fades.set(win, pending)
    pending.delay = setTimeout(() => {
        if (win.isDestroyed()) return fades.delete(win)
        win.webContents.send('visibility', false)
        pending.fade = setTimeout(() => {
            fades.delete(win)
            if (!win.isDestroyed()) win.hide()
        }, FADE_MS)
    }, delay)
}

function on_screen_bounds(saved, def) {
    const area = screen.getPrimaryDisplay().workArea
    const fallback = { ...def.size, x: area.x + area.width - def.size.width - 40, y: area.y + 80 }
    if (!saved) return fallback
    const visible = screen.getAllDisplays().some(d => {
        const a = d.workArea
        return saved.x < a.x + a.width - 40 && saved.x + saved.width > a.x + 40 && saved.y >= a.y - 10 && saved.y < a.y + a.height - 40
    })
    return visible ? saved : fallback
}

// ---------------------------------------------------------------- login window

function show_login() {
    for (const win of overlays.values()) conceal(win)
    conceal(mascot_win, { instant: true })
    if (!login_win || login_win.isDestroyed()) {
        login_win = base_window({ width: 400, height: 300 })
        login_win.loadFile(path.join(RENDERER, 'login.html'))
        login_win.once('ready-to-show', () => reveal(login_win, { activate: true }))
        login_win.on('closed', () => {
            login_win = null
            if (!state.user && !quitting) app.quit()
        })
    } else {
        reveal(login_win, { activate: true })
    }
}

// ---------------------------------------------------------------- overlay windows

function window_enabled(id) {
    const saved = (settings.get('windows') || {})[id]
    return saved && typeof saved.enabled === 'boolean' ? saved.enabled : window_def(id).default_enabled
}

function save_window(id, patch) {
    const windows = { ...(settings.get('windows') || {}) }
    windows[id] = { ...(windows[id] || {}), ...patch }
    settings.set('windows', windows)
}

function create_overlay(def) {
    const saved = (settings.get('windows') || {})[def.id] || {}
    const win = base_window({ ...on_screen_bounds(saved.bounds, def), minWidth: def.min_size.width, minHeight: def.min_size.height })
    overlays.set(def.id, win)
    win.loadFile(path.join(RENDERER, def.page))
    win.once('ready-to-show', () => {
        apply_mode()
        reveal_overlays()
    })
    const save_bounds = debounce(() => { if (!win.isDestroyed()) save_window(def.id, { bounds: win.getBounds() }) }, 400)
    win.on('move', save_bounds)
    win.on('resize', save_bounds)
    win.on('close', event => {
        if (quitting || win.__destroying) return
        event.preventDefault()   // × hides to the tray; Settings or the tray bring it back
        hidden.add(def.id)
        conceal(win)
    })
    win.on('closed', () => overlays.delete(def.id))
    return win
}

function destroy_overlay(id) {
    const win = overlays.get(id)
    if (!win || win.isDestroyed()) return
    win.__destroying = true
    win.close()
}

// Create/show every enabled window (after sign-in, from the tray, or a second launch).
function show_windows() {
    if (login_win && !login_win.isDestroyed()) login_win.destroy()
    for (const def of OVERLAY_WINDOWS) {
        if (!window_enabled(def.id)) continue
        hidden.delete(def.id)
        if (!overlays.has(def.id)) create_overlay(def)
    }
    reveal_overlays()
    start_refresh()
}

function set_window_enabled(id, enabled) {
    if (!window_def(id)) return
    save_window(id, { enabled })
    if (enabled) {
        hidden.delete(id)
        if (state.user && !overlays.has(id)) create_overlay(window_def(id))
        reveal_overlays()
        WINDOW_LOADERS[id]?.()   // a window enabled mid-session has no data yet
    } else {
        destroy_overlay(id)
    }
    update_tray()
    push_state()
}

// Overlay mode = always above EVE, never takes focus, click-through except the window's controls,
// and (with "Only over EVE") only visible while a logged-in EVE client or this app is in front.
function apply_mode() {
    const overlay = settings.get('overlay')
    for (const [id, win] of overlays) {
        if (win.isDestroyed()) continue
        win.setAlwaysOnTop(overlay, 'screen-saver')
        win.setFocusable(!overlay)
        win.setSkipTaskbar(overlay)
        win.setIgnoreMouseEvents(overlay, overlay ? { forward: true } : undefined)
        if (!overlay && !hidden.has(id)) reveal(win)   // unpinned windows don't follow EVE's focus
    }
    update_overlay_visibility()
    update_tray()
    push_state()
}

function reveal_overlays() {
    if (!settings.get('overlay')) {
        for (const [id, win] of overlays) if (!hidden.has(id)) reveal(win, { activate: true })
        return
    }
    update_overlay_visibility({ force: true })
}

function helper_starting() {
    return eve.supported && !eve.ready && !eve.failed   // ~0.3-1 s after launch: don't guess and flash
}

function own_pids() {
    return new Set(app.getAppMetrics().map(m => m.pid))
}

function update_overlay_visibility({ force = false } = {}) {
    update_mascot()
    if (!settings.get('overlay') || helper_starting()) return
    const show = overlay_should_show({
        helper_ready: eve.ready,
        eve_running: eve.eve_running,
        foreground: eve.foreground,
        own_pids: own_pids(),
        only_over_eve: settings.get('only_over_eve'),
    })
    const targets = [...overlays].filter(([id, win]) => !win.isDestroyed() && !hidden.has(id)).map(([, win]) => win)
    if (settings_win && !settings_win.isDestroyed() && settings_win.__wanted) targets.push(settings_win)
    for (const win of targets) {
        if (show || (force && show === null)) {
            reveal(win)
            win.moveTop()
        } else if (show === false) {
            conceal(win, hide_instantly(eve.foreground) ? { instant: true } : { delay: HIDE_DELAY_MS })
        }
    }
}

// ---------------------------------------------------------------- Sneak (opens Settings)

function ensure_mascot() {
    if (mascot_win && !mascot_win.isDestroyed()) return mascot_win
    mascot_win = base_window({
        width: 40, height: 36, focusable: false, skipTaskbar: true, alwaysOnTop: true, title: 'Minmatar Fleet',
    })
    mascot_win.setAlwaysOnTop(true, 'screen-saver')
    mascot_win.setIgnoreMouseEvents(true, { forward: true })   // only Sneak himself takes clicks
    mascot_win.loadFile(path.join(RENDERER, 'mascot.html'))
    mascot_win.on('closed', () => { mascot_win = null })
    return mascot_win
}

function active_client() {
    return eve.clients.find(c => c.hwnd === active_hwnd) || null
}

function update_mascot() {
    if (!eve || !settings) return
    if (eve.foreground.client && is_logged_in_client(eve.foreground)) active_hwnd = eve.foreground.hwnd
    const client = active_client()
    const wanted = state.user && settings.get('show_sneak') && !helper_starting()
    const show = wanted ? mascot_should_show({ helper_ready: eve.ready, foreground: eve.foreground, own_pids: own_pids(), active_client: client }) : false
    if (show === false) return conceal(mascot_win, { instant: !mascot_win || hide_instantly(eve.foreground) })
    if (show === null && !(mascot_win && mascot_win.isVisible())) return
    const win = ensure_mascot()
    const physical = mascot_rect(client, { offset: state.eve_window.badge_offset, scale: state.eve_window.ui_scale })
    const dip = screen.screenToDipRect(null, physical)
    win.setBounds({ x: Math.round(dip.x), y: Math.round(dip.y), width: Math.max(16, Math.round(dip.width)), height: Math.max(16, Math.round(dip.height)) })
    if (win.webContents.isLoading()) win.webContents.once('did-finish-load', () => { reveal(win); win.moveTop() })
    else { reveal(win); win.moveTop() }
}

// ---------------------------------------------------------------- Settings window

// Settings behaves like the overlays: no taskbar button and it never takes focus, so EVE stays the active
// window (an active non-EVE window makes Windows pop the taskbar over a Fixed Window client). Clicks still
// work on a window that can't be focused; it only needs the mouse.
function open_settings() {
    if (settings_win && !settings_win.isDestroyed()) {
        settings_win.__wanted = true
        reveal(settings_win)
        settings_win.moveTop()
        return
    }
    const area = screen.getDisplayNearestPoint(screen.getCursorScreenPoint()).workArea
    settings_win = base_window({
        width: 420, height: 680,
        x: Math.round(area.x + (area.width - 420) / 2), y: Math.round(area.y + Math.max(0, (area.height - 680) / 2)),
        focusable: false, skipTaskbar: true, alwaysOnTop: true,
    })
    settings_win.__wanted = true
    settings_win.setAlwaysOnTop(true, 'screen-saver')
    settings_win.loadFile(path.join(RENDERER, 'settings.html'))
    settings_win.once('ready-to-show', () => { reveal(settings_win); settings_win.moveTop() })
    settings_win.on('closed', () => { settings_win = null })
}

function set_user_setting(key, value) {
    if (!USER_SETTINGS.includes(key) || typeof value !== 'boolean') return
    settings.set(key, value)
    if (key === 'overlay') apply_mode()
    else update_overlay_visibility({ force: true })
    update_tray()
    push_state()
}

// ---------------------------------------------------------------- data

function fetch_error(err, what) {
    return err instanceof ApiError && err.status === 403
        ? `Your account does not have access to ${what}.`
        : 'Could not reach Minmatar Fleet. Retrying…'
}

// Each window's data loads on its own, so a slow campaign request never holds back the fleets list.
// A load already in flight is reused rather than started twice (interval tick, refresh button, enabling a window).
const in_flight = new Map()   // source -> promise

function load(source, fetcher, apply) {
    if (!state.user) return Promise.resolve()
    if (in_flight.has(source)) return in_flight.get(source)
    const done = (async () => {
        try {
            const value = await fetcher()
            if (state.user) apply(value, null)   // not if the pilot signed out meanwhile
        } catch (err) {
            diag({ t: 'refresh-error', source, status: err.status, message: err.message })
            if (!state.user) return
            if (err instanceof ApiError && err.status === 401) return sign_out('Your session has expired. Sign in again.')
            apply(null, err)
        }
    })().finally(() => {
        in_flight.delete(source)
        state.loading = in_flight.size > 0
        push_state()
    })
    in_flight.set(source, done)
    state.loading = true
    push_state()
    return done
}

function refresh_fleets() {
    return load('fleets', () => load_upcoming_fleets(api, config.web_url), (fleets, err) => {
        if (err) return void (state.error = fetch_error(err, 'fleets'))
        state.fleets = fleets
        state.error = null
        state.updated_at = new Date().toISOString()
    })
}

function refresh_campaign() {
    return load('campaign', () => load_campaign(api, config.web_url), (campaign, err) => {
        if (err) return void (state.campaign_error = fetch_error(err, 'campaigns'))
        state.campaign = campaign
        state.campaign_error = null
        state.campaign_updated_at = new Date().toISOString()
    })
}

const WINDOW_LOADERS = { fleets: refresh_fleets, campaigns: refresh_campaign }

// Data for the windows the pilot has enabled; a disabled window costs no requests.
function refresh() {
    for (const [id, loader] of Object.entries(WINDOW_LOADERS)) if (window_enabled(id)) loader()
}

function start_refresh() {
    clearInterval(refresh_timer)
    refresh()
    refresh_timer = setInterval(refresh, config.refresh_ms)
}

async function verify_session() {
    const me = await api.me()
    const character = me.eve_character_profile
    state.user = {
        name: character ? character.character_name : me.username,
        character_id: character ? character.character_id : null,
        avatar: me.discord_user_profile ? me.discord_user_profile.avatar : null,
    }
    diag({ t: 'signed-in', user_id: me.user_id })
}

async function begin_login() {
    if (login_flow) return
    state.login = { pending: true, error: null }
    push_state()
    login_flow = start_login({ api_url: config.api_url, open_external: url => shell.openExternal(url) })
    try {
        const token = await login_flow.promise
        const persisted = tokens.save(token)
        if (!persisted) diag({ t: 'token-not-persisted', reason: 'safeStorage unavailable' })
        await verify_session()
        state.login = { pending: false, error: null }
        update_tray()
        show_windows()
    } catch (err) {
        tokens.clear()
        state.user = null
        const message = err instanceof LoginCancelled ? null
            : err instanceof LoginFailed ? `Discord login failed (${err.code}${err.error_id ? `, ref ${err.error_id}` : ''}).`
            : err instanceof ApiError ? 'Signed in, but the Minmatar Fleet API rejected the session.'
            : 'Could not complete sign-in.'
        diag({ t: 'login-error', message: err.message })
        state.login = { pending: false, error: message }
    } finally {
        login_flow = null
        push_state()
    }
}

function sign_out(reason = null) {
    clearInterval(refresh_timer)
    tokens.clear()
    state.user = null
    state.fleets = []
    state.campaign = null
    state.campaign_error = null
    state.campaign_updated_at = null
    state.login = { pending: false, error: reason }
    if (settings_win && !settings_win.isDestroyed()) settings_win.close()
    show_login()
    update_tray()
    push_state()
}

// Match the transparency of whichever character's client is in front ("EVE - <name>" -> ID).
let front_name = null
async function follow_front_character() {
    if (!eve_window || !eve.foreground.client) return
    const name = (/^EVE - (.+)$/.exec(eve.foreground.title || '') || [])[1]
    if (!name || name === front_name) return
    front_name = name
    update_location()
    // The log engine already knows name -> ID for characters logged in on this PC; ESI is the fallback.
    const known = eve_logs && eve_logs.character_by_name(name)
    const character_id = (known && known.id) || await character_id_for_name(name)
    if (character_id && name === front_name) eve_window.set_character(character_id)
}

function update_location() {
    const name = front_name || (state.user && state.user.name)
    const c = name && eve_logs ? eve_logs.character_by_name(name) : null
    const next = c && c.system ? { character: c.name, system: c.system } : null
    if (JSON.stringify(next) === JSON.stringify(state.location)) return
    state.location = next
    push_state()
}

function push_state() {
    if (!settings) return
    const payload = {
        ...state,
        version: app.getVersion(),
        overlay: settings.get('overlay'),
        settings: Object.fromEntries(USER_SETTINGS.map(k => [k, settings.get(k)])),
        windows: OVERLAY_WINDOWS.map(def => ({ id: def.id, title: def.title, description: def.description, enabled: window_enabled(def.id) })),
        glass: glass_ready,
        eve_running: eve ? eve.eve_running : false,
        api_url: config.api_url,
        notice: CCP_NOTICE,
        updater_enabled: !!(updater && updater.enabled),
    }
    for (const win of all_windows()) win.webContents.send('state', payload)
}

// ---------------------------------------------------------------- tray

function update_menu_items() {
    const u = state.update
    if (u.status === 'ready') return [{ label: `Restart to update (v${u.version})`, click: () => install_update() }]
    if (u.status === 'available') return [{ label: `Download v${u.version}…`, click: () => shell.openExternal(RELEASES_URL) }]
    if (u.status === 'downloading') return [{ label: `Downloading v${u.version}… ${u.percent || 0}%`, enabled: false }]
    return []
}

function install_update() {
    quitting = true
    updater.install()
}

function update_tray() {
    if (!tray) return
    const signed_in = !!state.user
    tray.setToolTip(`Minmatar Fleet ${app.getVersion()}${signed_in ? ` — ${state.user.name}` : ''}`)
    tray.setContextMenu(Menu.buildFromTemplate([
        { label: 'Show windows', enabled: signed_in, click: () => show_windows() },
        { label: 'Settings…', enabled: signed_in, click: () => open_settings() },
        { label: 'Refresh', enabled: signed_in, click: refresh },
        { type: 'separator' },
        ...update_menu_items(),
        signed_in ? { label: `Sign out (${state.user.name})`, click: () => sign_out() } : { label: 'Sign in…', click: show_login },
        { label: `Quit (v${app.getVersion()})`, click: () => { quitting = true; app.quit() } },
    ]))
}

// ---------------------------------------------------------------- IPC (renderer -> main)

function sender_window(event) {
    return BrowserWindow.fromWebContents(event.sender)
}

ipcMain.on('login:start', () => begin_login())
ipcMain.on('login:cancel', () => login_flow && login_flow.cancel())
ipcMain.on('auth:sign-out', () => sign_out())
ipcMain.on('fleets:refresh', () => refresh())
ipcMain.on('fleets:open', (event, fleet_id) => {
    // Only open URLs we built ourselves, never one supplied by the renderer.
    const fleet = state.fleets.find(f => f.id === fleet_id)
    if (fleet) shell.openExternal(fleet.url)
})
ipcMain.on('campaigns:open', () => {
    // Same rule as fleets: only a URL we built.
    if (state.campaign) shell.openExternal(state.campaign.url)
})
ipcMain.on('update:install', () => install_update())
ipcMain.on('update:download', () => { if (state.update.status === 'available') shell.openExternal(RELEASES_URL) })
ipcMain.on('update:check', () => updater && updater.check())
ipcMain.on('settings:open', () => { if (state.user) open_settings() })
ipcMain.on('settings:set', (event, change) => change && set_user_setting(change.key, change.value))
ipcMain.on('window:set-enabled', (event, change) => change && typeof change.enabled === 'boolean' && set_window_enabled(change.id, change.enabled))
ipcMain.on('overlay:toggle', () => set_user_setting('overlay', !settings.get('overlay')))
ipcMain.on('window:minimize', event => {
    const win = sender_window(event)
    const id = overlay_id_of(win)
    if (id && settings.get('overlay')) {
        hidden.add(id)   // overlays have no taskbar button: "minimise" hides until the tray or Settings brings it back
        conceal(win)
    } else if (win) {
        win.minimize()
    }
})
ipcMain.on('window:close', event => {
    const win = sender_window(event)
    if (win) win.close()
})
ipcMain.on('mouse:interactive', (event, interactive) => {
    const win = sender_window(event)
    if (win && (win === mascot_win || (overlay_id_of(win) && settings.get('overlay')))) {
        win.setIgnoreMouseEvents(!interactive, interactive ? undefined : { forward: true })
    }
})
let resize_start = null
ipcMain.on('resize:start', (event, point) => {
    const win = sender_window(event)
    if (win) resize_start = { point, bounds: win.getBounds(), min: window_def(overlay_id_of(win))?.min_size || { width: 320, height: 220 } }
})
ipcMain.on('resize:move', (event, point) => {
    const win = sender_window(event)
    if (!win || !resize_start) return
    win.setBounds({
        ...resize_start.bounds,
        width: Math.max(resize_start.min.width, Math.round(resize_start.bounds.width + point.x - resize_start.point.x)),
        height: Math.max(resize_start.min.height, Math.round(resize_start.bounds.height + point.y - resize_start.point.y)),
    })
})
ipcMain.on('resize:end', () => { resize_start = null })

// ---------------------------------------------------------------- lifecycle

function debounce(fn, ms) {
    let t
    return (...args) => { clearTimeout(t); t = setTimeout(() => fn(...args), ms) }
}

app.on('second-instance', () => {
    state.user ? show_windows() : show_login()
})

function migrate_settings() {
    // 0.4: per-window settings; the fleets window's position used to be a top-level key.
    if (settings.get('fleets_bounds') && !(settings.get('windows') || {}).fleets) save_window('fleets', { bounds: settings.get('fleets_bounds') })
}

app.whenReady().then(async () => {
    if (process.platform === 'win32') app.setAppUserModelId('org.minmatar.desktop')
    const user_data = app.getPath('userData')
    settings = new Settings(path.join(user_data, 'settings.json'), { overlay: true, only_over_eve: true, show_sneak: true, windows: {} })
    migrate_settings()
    settings.set('overlay', true)   // every launch starts pinned over EVE; the pin button unpins for the session
    tokens = new TokenStore(path.join(user_data, 'session.bin'), safeStorage)
    api = new ApiClient({ api_url: config.api_url, get_token: () => tokens.load() })

    eve = new EveClients({ user_data_dir: user_data, client_procs: config.client_procs })
    eve.on('ready', () => {
        glass_ready = true
        for (const win of all_windows()) if (win !== mascot_win) eve.apply_glass(win)
        push_state()
        update_overlay_visibility({ force: true })
    })
    eve.on('change', () => {
        update_overlay_visibility()
        follow_front_character()
        push_state()
    })
    eve.on('client-front', () => setTimeout(update_overlay_visibility, 300))   // EVE can land above us for a frame
    eve.on('log', diag)
    eve.start()

    const logs_arg = process.argv.find(a => a.startsWith('--logs='))
    eve_logs = new EveLogEngine({ logs_dir: logs_arg ? logs_arg.slice(7) : path.join(app.getPath('documents'), 'EVE', 'logs') })
    eve_logs.on('ready', snapshot => { diag({ t: 'logs-ready', characters: snapshot.characters.length, sessions: snapshot.sessions }); update_location() })
    eve_logs.on('system', event => { diag({ t: 'system', character: event.character.name, from: event.from, to: event.to, source: event.source }); update_location() })
    eve_logs.on('error', err => diag({ t: 'logs-error', message: err.message }))
    eve_logs.start()

    if (process.platform === 'win32' && process.env.LOCALAPPDATA) {
        eve_window = new EveWindowSettings({ local_app_data: process.env.LOCALAPPDATA })
        eve_window.on('change', value => {
            state.eve_window = value
            diag({ t: 'eve-window-settings', ...value })
            update_mascot()
            push_state()
        })
        eve_window.start()
    }

    updater = new Updater({ app, diag })
    updater.on('change', update => { state.update = update; update_tray(); push_state() })
    updater.start()

    tray = new Tray(nativeImage.createFromPath(path.join(ASSETS, 'tray.png')))
    tray.on('click', () => { state.user ? show_windows() : show_login() })
    update_tray()

    diag({ t: 'start', version: app.getVersion(), api_url: config.api_url, can_persist_token: tokens.can_persist() })

    if (tokens.load()) {
        try {
            await verify_session()
            update_tray()
            show_windows()
            return
        } catch (err) {
            diag({ t: 'stored-session-check-failed', status: err.status, message: err.message })
            if (err instanceof ApiError && err.status === 401) {
                tokens.clear()
                state.login.error = 'Your session has expired. Sign in again.'
            } else {
                // Offline or API down: keep the stored session and let the refresh loop retry.
                const payload = decode_token_payload(tokens.load()) || {}
                state.user = { name: payload.username || 'Pilot', character_id: null, avatar: payload.avatar || null }
                update_tray()
                show_windows()
                return
            }
        }
    }
    show_login()
})

app.on('before-quit', () => {
    quitting = true
    clearInterval(refresh_timer)
    if (eve) eve.stop()
    if (eve_window) eve_window.stop()
    if (eve_logs) eve_logs.stop()
    if (updater) updater.stop()
})
app.on('window-all-closed', () => {})
