// Minmatar Fleet desktop app: Discord sign-in, EVE-styled overlay windows (see windows.js) pinned as glass
// over the EVE client, a Sneak mascot on EVE's notification badge that opens Settings, and the tray.
const { app, BrowserWindow, ipcMain, shell, safeStorage, screen, Tray, Menu, nativeImage, clipboard, Notification } = require('electron')
const fs = require('fs')
const path = require('path')
const { load_config } = require('./config')
const { start_login, decode_token_payload, TokenStore, LoginCancelled, LoginFailed } = require('./auth')
const { ApiClient, ApiError, load_upcoming_fleets, load_campaign } = require('./api')
const { EveClients } = require('./eve_clients')
const { Settings } = require('./settings')
const { EveWindowSettings, character_id_for_name } = require('./eve_settings')
const { overlay_should_show, mascot_should_show, is_logged_in_client, client_on_screen, hide_instantly } = require('./overlay_rules')
const { EveLogEngine } = require('./eve_logs')
const { Updater, RELEASES_URL } = require('./updater')
const { OVERLAY_WINDOWS, window_def } = require('./windows')
const { mascot_rect } = require('./mascot')
const { FleetWindow } = require('./fleet_window')
const { RouteFinder } = require('./route')
const { IntelController } = require('./intel')

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

// Settings the Settings window may change (booleans only), saved on the account (settings.js).
// "locked" is the pin button: whether the windows can be dragged and resized.
const USER_SETTINGS = ['locked', 'show_sneak', 'intel_alerts']
const SETTINGS_DEFAULTS = { locked: true, show_sneak: true, intel_alerts: true }
const INTEL_DEFAULT_RANGE = 5   // jumps
const SESSION_SETTINGS = []
const SETTINGS_WAIT_MS = 3000   // how long a sign-in waits for the account's settings before showing defaults

function diag(entry) {
    const line = JSON.stringify({ ts: new Date().toISOString(), ...entry })
    console.log(line)
    if (DIAG) try { fs.appendFileSync(DIAG, line + '\n') } catch (e) {}
}

if (!app.requestSingleInstanceLock()) app.exit(0)   // already running: the first instance gets "second-instance" and shows itself

let tokens, settings, api, eve, eve_window, eve_logs, updater, tray, fleet_window, intel
let LEGACY_SETTINGS_FILE = null
let login_win = null
let settings_win = null
let mascot_win = null
const overlays = new Map()       // window id -> BrowserWindow
const hidden = new Set()         // overlay ids closed/minimised this session (the tray or Settings brings them back)
let active_hwnd = null           // last logged-in EVE client that was in front (Sneak sits on its badge)
let login_flow = null
let refresh_timer = null
let list_refreshed_at = 0
let fleet_snapshot = null        // what the Fleets window's fleet view shows (fleet_window.js), sent on its own channel
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
    // Intel window (intel.js view()); only fetched while that window is enabled.
    intel: null,
}

// ---------------------------------------------------------------- window plumbing

function base_window(options) {
    const win = new BrowserWindow({
        frame: false,
        transparent: true,
        backgroundColor: '#00000000',
        resizable: false,          // transparent windows can't use native edge-resize on Windows; we use a grip
        thickFrame: false,         // no WS_CAPTION: Windows would paint its own title bar over the page on header clicks
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
        if (overlay_id_of(win) === 'fleets') win.webContents.send('fleet', fleet_snapshot)
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

// Each window's settings are one key ("window.fleets": { enabled, bounds }) so a change to one window
// never overwrites another's on the account.
const window_key = id => `window.${id}`

function window_saved(id) {
    return settings.get(window_key(id)) || {}
}

function window_enabled(id) {
    const saved = window_saved(id)
    return typeof saved.enabled === 'boolean' ? saved.enabled : window_def(id).default_enabled
}

function save_window(id, patch) {
    settings.set(window_key(id), { ...window_saved(id), ...patch })
}

// Moves made by the app (restoring a saved spot, or the fallback when it's off this PC's screens) are
// not saved, so a position from another PC's monitor layout is only replaced when the pilot moves the window.
function place(win, bounds) {
    win.setBounds(bounds)
    win.__placed = JSON.stringify(win.getBounds())
}

function create_overlay(def) {
    // Overlay windows never take focus (only Intel, while a report is written: intel_typing) and are
    // click-through except their controls, so EVE stays the active window.
    const win = base_window({
        ...on_screen_bounds(window_saved(def.id).bounds, def), minWidth: def.min_size.width, minHeight: def.min_size.height,
        focusable: false, skipTaskbar: true,
    })
    win.setIgnoreMouseEvents(true, { forward: true })
    win.__placed = JSON.stringify(win.getBounds())
    overlays.set(def.id, win)
    win.loadFile(path.join(RENDERER, def.page))
    win.once('ready-to-show', () => update_overlay_visibility({ force: true }))
    const save_bounds = debounce(() => {
        if (win.isDestroyed()) return
        const bounds = win.getBounds()
        if (JSON.stringify(bounds) !== win.__placed) save_window(def.id, { bounds })
    }, 400)
    win.on('move', save_bounds)
    win.on('resize', save_bounds)
    win.on('close', event => {
        if (quitting || win.__destroying) return
        event.preventDefault()   // × hides to the tray; Settings or the tray bring it back
        hidden.add(def.id)
        conceal(win)
        update_polling()
    })
    win.on('closed', () => { overlays.delete(def.id); update_polling() })
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
    update_polling()
    sync_intel()
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
    update_polling()
    sync_intel()
    update_tray()
    push_state()
}

function reveal_overlays() {
    update_overlay_visibility({ force: true })
}

function helper_starting() {
    return eve.supported && !eve.ready && !eve.failed   // ~0.3-1 s after launch: don't guess and flash
}

function own_pids() {
    return new Set(app.getAppMetrics().map(m => m.pid))
}

// The windows live on EVE: not always-on-top, the helper stacks them directly above the client instead,
// so an app brought in front of EVE (Discord, a browser) covers them like it covers EVE, and they hide
// when no logged-in client is on screen (overlay_rules.js). Only without the helper (not Windows, or
// PowerShell blocked) is there nothing to sit on; then they float over everything.
function stays_with_eve() {
    return !!(eve && eve.ready && eve.eve_running)
}

function set_topmost(win, on) {
    if (win.__topmost === on) return
    win.__topmost = on
    win.setAlwaysOnTop(on, 'screen-saver')
}

// The client the windows sit on: the last logged-in client in front, or another logged-in one on screen
// when that one is minimised or gone.
function stack_client() {
    const active = active_client()
    if (client_on_screen(active)) return active
    return eve.clients.find(client_on_screen) || active
}

// All visible pinned windows go in one call, so they keep one run directly above the client (helper.cs Stack).
function stack_windows() {
    const client = stack_client()
    if (!client) return
    const wins = [...overlays].filter(([id, win]) => !win.isDestroyed() && !hidden.has(id) && win.isVisible()).map(([, win]) => win)
    if (mascot_win && !mascot_win.isDestroyed() && mascot_win.isVisible()) wins.push(mascot_win)
    eve.stack(client.hwnd, wins)
}

function update_overlay_visibility({ force = false } = {}) {
    update_mascot()
    if (!settings) return
    const stay = stays_with_eve()
    for (const win of overlays.values()) if (!win.isDestroyed()) set_topmost(win, !stay)
    if (helper_starting()) return
    const rule = {
        helper_ready: eve.ready,
        eve_running: eve.eve_running,
        foreground: eve.foreground,
        own_pids: own_pids(),
    }
    const show = overlay_should_show({ ...rule, active_client: stack_client() })
    const targets = [...overlays].filter(([id, win]) => !win.isDestroyed() && !hidden.has(id)).map(([, win]) => [win, show])
    // Settings stays above every app, so it still hides when another app comes in front of EVE. With no
    // client running it shows anyway: the tray opens it before the game is up.
    if (settings_win && !settings_win.isDestroyed() && settings_win.__wanted) {
        targets.push([settings_win, !eve.eve_running || overlay_should_show({ ...rule, active_client: null })])
    }
    for (const [win, shown] of targets) {
        if (shown || (force && shown === null)) {
            reveal(win)
            if (!stay || win === settings_win) win.moveTop()
        } else if (shown === false) {
            conceal(win, hide_instantly(eve.foreground) ? { instant: true } : { delay: HIDE_DELAY_MS })
        }
    }
    if (stay) stack_windows()
}

// ---------------------------------------------------------------- Sneak (opens Settings)

function ensure_mascot() {
    if (mascot_win && !mascot_win.isDestroyed()) return mascot_win
    mascot_win = base_window({
        width: 40, height: 36, focusable: false, skipTaskbar: true, alwaysOnTop: true, title: 'Minmatar Fleet',
    })
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
    const stay = stays_with_eve()
    const show = wanted ? mascot_should_show({ helper_ready: eve.ready, foreground: eve.foreground, own_pids: own_pids(), active_client: client }) : false
    if (show === false) return conceal(mascot_win, { instant: !mascot_win || hide_instantly(eve.foreground) })
    if (show === null && !(mascot_win && mascot_win.isVisible())) return
    const win = ensure_mascot()
    set_topmost(win, !stay)
    const physical = mascot_rect(client, { offset: state.eve_window.badge_offset, scale: state.eve_window.ui_scale })
    const dip = screen.screenToDipRect(null, physical)
    win.setBounds({ x: Math.round(dip.x), y: Math.round(dip.y), width: Math.max(16, Math.round(dip.width)), height: Math.max(16, Math.round(dip.height)) })
    const raise = () => { reveal(win); stay ? stack_windows() : win.moveTop() }
    if (win.webContents.isLoading()) win.webContents.once('did-finish-load', raise)
    else raise()
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

// The account's settings arrived after the windows were already up on defaults (slow or down API at launch).
function apply_loaded_settings(keys) {
    diag({ t: 'settings-loaded', keys })
    if (!state.user) return
    for (const def of OVERLAY_WINDOWS) {
        if (!keys.includes(window_key(def.id))) continue
        const win = overlays.get(def.id)
        if (!window_enabled(def.id)) destroy_overlay(def.id)
        else if (!win) {
            create_overlay(def)
            WINDOW_LOADERS[def.id]?.()   // enabled by the account's settings: it has no data yet
        } else if (window_saved(def.id).bounds && !win.isDestroyed()) place(win, on_screen_bounds(window_saved(def.id).bounds, def))
    }
    update_overlay_visibility({ force: true })
    sync_intel()
    update_tray()
    push_state()
}

// Wait briefly for the account's settings so windows open where the pilot left them. If the API is slow
// or down, go ahead on defaults: settings.js keeps retrying and apply_loaded_settings catches up.
function load_settings() {
    return Promise.race([settings.load(), new Promise(resolve => setTimeout(resolve, SETTINGS_WAIT_MS))])
}

// 0.4 test builds kept settings in settings.json; carry them to the account once, then delete the file.
function adopt_local_settings_file(remote_values) {
    if (Object.keys(remote_values).length || !fs.existsSync(LEGACY_SETTINGS_FILE)) return
    let legacy
    try { legacy = JSON.parse(fs.readFileSync(LEGACY_SETTINGS_FILE, 'utf8')) } catch (e) { legacy = {} }
    for (const key of USER_SETTINGS) if (!SESSION_SETTINGS.includes(key) && typeof legacy[key] === 'boolean') settings.set(key, legacy[key])
    const windows = { ...(legacy.windows || {}) }
    if (legacy.fleets_bounds && !windows.fleets) windows.fleets = { bounds: legacy.fleets_bounds }
    for (const [id, saved] of Object.entries(windows)) if (window_def(id) && saved) settings.set(window_key(id), saved)
    diag({ t: 'settings-file-adopted' })
    apply_loaded_settings(OVERLAY_WINDOWS.map(def => window_key(def.id)))
    settings.once('saved', () => { try { fs.unlinkSync(LEGACY_SETTINGS_FILE) } catch (e) {} })
}

function set_user_setting(key, value) {
    if (!USER_SETTINGS.includes(key) || typeof value !== 'boolean') return
    settings.set(key, value)
    if (key === 'intel_alerts') intel.set_options({ alerts: value })
    else if (key !== 'locked') update_overlay_visibility({ force: true })   // "locked" only changes the windows' drag region and grip
    update_polling()
    update_tray()
    push_state()
}

// ---------------------------------------------------------------- data

// The fleet list and the fleet view poll only while the Fleets window is up: not closed to the tray,
// and not while EVE isn't running, when the window can't show anyway.
function polling_wanted() {
    if (!state.user || !settings) return false
    const win = overlays.get('fleets')
    if (!win || win.isDestroyed() || hidden.has('fleets')) return false
    return !eve || !eve.supported || eve.failed || eve.eve_running
}

function update_polling() {
    if (!fleet_window) return
    const wanted = polling_wanted()
    fleet_window.set_active(wanted)
    if (wanted && list_wanted() && Date.now() - list_refreshed_at >= config.refresh_ms) refresh_fleets()
}

// The upcoming list is only fetched while it's on screen; the fleet view has its own poll.
function list_wanted() {
    return polling_wanted() && (!fleet_snapshot || fleet_snapshot.view === 'list')
}

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

// The upcoming list is only fetched while it's on screen (force: the refresh button and tray).
function refresh_fleets({ force = false } = {}) {
    if (!force && !list_wanted()) return Promise.resolve()
    list_refreshed_at = Date.now()
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
function refresh({ force = false } = {}) {
    for (const [id, loader] of Object.entries(WINDOW_LOADERS)) if (window_enabled(id)) loader({ force })
}

function start_refresh() {
    clearInterval(refresh_timer)
    refresh()
    refresh_timer = setInterval(refresh, config.refresh_ms)
}

// ---------------------------------------------------------------- intel

// Poll the intel sheet only while the Intel window is on.
function sync_intel() {
    const on = !!state.user && window_enabled('intel')
    if (on && !intel.timer) {
        const range = window_saved('intel').range
        intel.set_options({ range: range === undefined ? INTEL_DEFAULT_RANGE : range, alerts: settings.get('intel_alerts') })
        intel.set_origin(state.location)
        intel.start()
    } else if (!on && intel.timer) {
        intel.stop()
    }
}

// Typing a note needs keyboard focus, which overlay windows never take. Let the Intel window take it
// while a report is being written, and give it back after.
function intel_typing(on) {
    const win = overlays.get('intel')
    if (!win || win.isDestroyed()) return
    if (on) {
        win.setFocusable(true)
        win.setIgnoreMouseEvents(false)
        win.focus()
    } else if (win.isFocusable()) {
        win.setFocusable(false)
        win.setIgnoreMouseEvents(true, { forward: true })
    }
}

const KIND_TITLES = { caps: 'Capital ping', fleet: 'Fleet ping' }

// Alerts only inform (CCP rule 2): a Windows notification for a new ping within range.
function notify_ping(item) {
    if (!Notification.isSupported()) return
    const where = item.jumps == null ? '' : item.jumps === 0 ? ' (here)' : ` (${item.jumps} ${item.jumps === 1 ? 'jump' : 'jumps'})`
    const toast = new Notification({
        title: `${KIND_TITLES[item.kind] || 'Intel'} · ${item.system_name}${where}`,
        body: item.summary,
        icon: path.join(ASSETS, 'icon.png'),
    })
    toast.on('click', () => { hidden.delete('intel'); show_windows() })
    toast.show()
    diag({ t: 'intel-ping', id: item.id })
}

async function verify_session() {
    const me = await api.me()
    const character = me.eve_character_profile
    state.user = {
        name: character ? character.character_name : me.username,
        character_id: character ? character.character_id : null,
        avatar: me.discord_user_profile ? me.discord_user_profile.avatar : null,
    }
    if (fleet_window) fleet_window.set_primary_character(state.user.character_id)
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
        await load_settings()
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
    fleet_window.reset()
    api.forget_cached()
    set_fleet_snapshot(null)
    intel.sign_out()
    settings.flush()   // starts with the current token, before it's cleared
    settings.reset()
    tokens.clear()
    for (const id of [...overlays.keys()]) destroy_overlay(id)   // the next pilot's windows open from their own settings
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
    if (fleet_window) fleet_window.set_front({ name: front_name, system: c && front_name && c.name === front_name ? c.system : null, id: c && c.id })
    if (JSON.stringify(next) === JSON.stringify(state.location)) return
    state.location = next
    if (intel) intel.set_origin(next)
    push_state()
}

function set_fleet_snapshot(snapshot) {
    fleet_snapshot = snapshot
    const win = overlays.get('fleets')
    if (win && !win.isDestroyed() && !win.webContents.isLoading()) win.webContents.send('fleet', snapshot)
}

function push_state() {
    if (!settings) return
    const payload = {
        ...state,
        version: app.getVersion(),
        locked: settings.get('locked'),
        settings_sync: settings.status,
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

async function install_update() {
    quitting = true
    await flush_settings_before_quit()
    updater.install()
}

// Quitting with unsaved changes (e.g. a window moved a moment ago): give the API a moment to take them.
const QUIT_FLUSH_MS = 2000
let quit_flushed = false
async function flush_settings_before_quit() {
    if (quit_flushed) return
    quit_flushed = true
    if (settings && settings.has_pending() && tokens.load()) {
        await Promise.race([settings.flush(), new Promise(resolve => setTimeout(resolve, QUIT_FLUSH_MS))])
    }
}

function update_tray() {
    if (!tray) return
    const signed_in = !!state.user
    tray.setToolTip(`Minmatar Fleet ${app.getVersion()}${signed_in ? ` — ${state.user.name}` : ''}`)
    tray.setContextMenu(Menu.buildFromTemplate([
        { label: 'Show windows', enabled: signed_in, click: () => show_windows() },
        { label: 'Settings…', enabled: signed_in, click: () => open_settings() },
        { label: 'Refresh', enabled: signed_in, click: () => { refresh({ force: true }); fleet_window.poll(); if (intel.timer) intel.refresh() } },
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
ipcMain.on('fleets:refresh', () => {
    refresh({ force: true })
    if (fleet_window && state.user) fleet_window.poll()
})
ipcMain.on('fleets:open', (event, fleet_id) => {
    // Opens the fleet in the window. Only fleets from the list, never an id the renderer made up.
    const fleet = state.fleets.find(f => f.id === fleet_id)
    if (fleet && fleet_window) fleet_window.open(fleet.id)
})
// Fleet view actions. Each is one click; keys are checked against the fleet's own ships in fleet_window.js.
const fleet_key = value => (typeof value === 'string' && /^[fm]:\d+$/.test(value) ? value : null)
ipcMain.on('fleet:back', () => fleet_window && fleet_window.back())
ipcMain.on('fleet:open-site', () => fleet_window && fleet_window.open_site())
ipcMain.on('fleet:refresh-motd', () => fleet_window && fleet_window.refresh_motd())
ipcMain.on('fleet:copy-fit', (event, key) => fleet_window && fleet_key(key) && fleet_window.copy_fit(key))
ipcMain.on('fleet:sign-up', (event, key) => fleet_window && fleet_key(key) && fleet_window.sign_up(key))
ipcMain.on('fleet:srp', () => fleet_window && fleet_window.file_srp())
ipcMain.on('fleet:dismiss-loss', () => fleet_window && fleet_window.dismiss_loss())
ipcMain.on('fleet:done', () => fleet_window && fleet_window.done())
ipcMain.on('campaigns:open', () => {
    // Same rule as fleets: only a URL we built.
    if (state.campaign) shell.openExternal(state.campaign.url)
})
ipcMain.on('intel:refresh', () => intel.refresh())
// The paste button reads the clipboard here, on the pilot's click; Ctrl+V in a focused window sends the text.
ipcMain.on('intel:paste', () => { intel_typing(true); intel.paste(clipboard.readText()) })
ipcMain.on('intel:paste-text', (event, text) => { intel_typing(true); intel.paste(text) })
ipcMain.on('intel:kind', (event, kind) => intel.set_kind(kind))
ipcMain.on('intel:edit', (event, change) => change && intel.edit_draft(change))
ipcMain.on('intel:share', async () => {
    const url = await intel.share()
    if (!url) return   // failed: the draft stays open for another try
    clipboard.writeText(url)
    intel_typing(false)
})
ipcMain.on('intel:discard', () => { intel.discard(); intel_typing(false) })
ipcMain.on('intel:open-report', (event, report_id) => intel.open_report(report_id))
ipcMain.on('intel:close-report', () => intel.close_report())
ipcMain.on('intel:copy-link', (event, report_id) => {
    const url = intel.url_for(report_id)
    if (url) clipboard.writeText(url)
})
ipcMain.on('intel:open-site', (event, report_id) => {
    const url = intel.url_for(report_id)
    if (url) shell.openExternal(url)
})
ipcMain.on('intel:range', (event, range) => {
    if (range !== null && !Number.isInteger(range)) return
    save_window('intel', { range })
    intel.set_options({ range })
})
ipcMain.on('update:install', () => install_update())
ipcMain.on('update:download', () => { if (state.update.status === 'available') shell.openExternal(RELEASES_URL) })
ipcMain.on('update:check', () => updater && updater.check())
ipcMain.on('settings:open', () => { if (state.user) open_settings() })
ipcMain.on('settings:set', (event, change) => change && set_user_setting(change.key, change.value))
ipcMain.on('window:set-enabled', (event, change) => change && typeof change.enabled === 'boolean' && set_window_enabled(change.id, change.enabled))
ipcMain.on('lock:toggle', () => set_user_setting('locked', !settings.get('locked')))
ipcMain.on('window:minimize', event => {
    const win = sender_window(event)
    const id = overlay_id_of(win)
    if (id) {
        hidden.add(id)   // overlays have no taskbar button: "minimise" hides until the tray or Settings brings it back
        conceal(win)
        update_polling()
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
    if (win && (win === mascot_win || overlay_id_of(win)) && !win.isFocusable()) {
        win.setIgnoreMouseEvents(!interactive, interactive ? undefined : { forward: true })
    }
})
let resize_start = null
ipcMain.on('resize:start', (event, point) => {
    const win = sender_window(event)
    if (win && !settings.get('locked')) resize_start = { point, bounds: win.getBounds(), min: window_def(overlay_id_of(win))?.min_size || { width: 320, height: 220 } }
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

app.whenReady().then(async () => {
    if (process.platform === 'win32') app.setAppUserModelId('org.minmatar.desktop')
    const user_data = app.getPath('userData')
    LEGACY_SETTINGS_FILE = path.join(user_data, 'settings.json')
    tokens = new TokenStore(path.join(user_data, 'session.bin'), safeStorage)
    api = new ApiClient({ api_url: config.api_url, get_token: () => tokens.load() })
    fleet_window = new FleetWindow({
        api,
        routes: new RouteFinder(),
        web_url: config.web_url,
        clipboard,
        open_external: url => shell.openExternal(url),
    })
    fleet_window.on('change', snapshot => {
        const back_to_list = snapshot.view === 'list' && fleet_snapshot && fleet_snapshot.view !== 'list'
        set_fleet_snapshot(snapshot)
        if (back_to_list && Date.now() - list_refreshed_at >= config.refresh_ms) refresh_fleets()
    })
    fleet_window.on('unauthorized', () => sign_out('Your session has expired. Sign in again.'))
    intel = new IntelController({
        api,
        web_url: config.web_url,
        on_change: view => { state.intel = view; push_state() },
        on_unauthorized: () => sign_out('Your session has expired. Sign in again.'),
        notify: notify_ping,
        diag,
    })
    settings = new Settings({
        defaults: SETTINGS_DEFAULTS,
        session_keys: SESSION_SETTINGS,
        remote: { load: () => api.desktop_settings(), save: values => api.save_desktop_settings(values) },
    })
    settings.on('loaded', adopt_local_settings_file)
    settings.on('change', apply_loaded_settings)
    settings.on('status', status => { diag({ t: 'settings-sync', status }); push_state() })
    settings.on('error', err => diag({ t: 'settings-error', ...err }))

    eve = new EveClients({ user_data_dir: user_data, client_procs: config.client_procs })
    eve.on('ready', () => {
        glass_ready = true
        for (const win of all_windows()) if (win !== mascot_win) eve.apply_glass(win)
        push_state()
        update_overlay_visibility({ force: true })
    })
    eve.on('change', () => {
        update_overlay_visibility()
        update_polling()
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
            await load_settings()
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
                settings.load()   // retries in the background; windows move into place when it lands
                update_tray()
                show_windows()
                return
            }
        }
    }
    show_login()
})

app.on('before-quit', event => {
    quitting = true
    if (!quit_flushed && settings && settings.has_pending()) {
        event.preventDefault()
        flush_settings_before_quit().finally(() => app.quit())
        return
    }
    clearInterval(refresh_timer)
    if (fleet_window) fleet_window.stop()
    if (intel) intel.stop()
    if (settings) settings.stop()
    if (eve) eve.stop()
    if (eve_window) eve_window.stop()
    if (eve_logs) eve_logs.stop()
    if (updater) updater.stop()
})
app.on('window-all-closed', () => {})
