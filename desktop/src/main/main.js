// Minmatar Fleet desktop app: Discord sign-in, EVE-styled overlay windows (see windows.js) pinned as glass
// over the EVE client, a Sneak mascot on EVE's notification badge that opens Settings, and the tray.
const { app, BrowserWindow, ipcMain, shell, safeStorage, screen, Tray, Menu, nativeImage, clipboard, Notification } = require('electron')
const fs = require('fs')
const path = require('path')
const { load_config } = require('./config')
const { start_login, decode_token_payload, TokenStore, LoginCancelled, LoginFailed } = require('./auth')
const { ApiClient, ApiError, client_id, is_unauthorized, load_upcoming_fleets, load_campaign } = require('./api')
const { EveClients } = require('./eve_clients')
const { Settings } = require('./settings')
const { EveWindowSettings, character_id_for_name } = require('./eve_settings')
const { overlay_should_show, mascot_should_show, is_logged_in_client, client_on_screen, hide_instantly } = require('./overlay_rules')
const { EveLogEngine } = require('./eve_logs')
const { Updater, RELEASES_URL, is_portable } = require('./updater')
const { OVERLAY_WINDOWS, window_def } = require('./windows')
const { mascot_rect } = require('./mascot')
const { FleetWindow } = require('./fleet_window')
const { RouteFinder } = require('./route')
const { IntelController, DEFAULT_RANGE: INTEL_DEFAULT_RANGE, REFRESH_MS: INTEL_REFRESH_MS } = require('./intel')
const { ClipboardWatch } = require('./clipboard_watch')
const { Poller, window_data_wanted } = require('./poller')
const { MenuFade, intersects } = require('./menu_fade')
const { COMMANDS, id_of, fleet_ship, intel_range, window_toggle } = require('./ipc_commands')
const { TOGGLES, read_toggle, window_key, stored_window, read_window } = require('./settings_schema')

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

// Settings the Settings window may change are the boolean TOGGLES in settings_schema.js, saved on the
// account (settings.js) with every other key there. "locked" is the pin button: whether the windows can
// be dragged and resized.
const USER_SETTINGS = Object.keys(TOGGLES)
const toggle = key => read_toggle(key, settings.get(key))
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
let reminder_timer = null
let pollers = {}                 // window id -> Poller for that window's data (created at start-up)
let intel_on = false             // the Intel window is enabled for the signed-in pilot
let clipboard_watch = null       // spots a d-scan or Local copy while the Intel window is up (clipboard_watch.js)
let fleet_snapshot = null        // what the Fleets window's fleet view shows (fleet_window.js), sent on its own channel
let quitting = false
let glass_ready = false
const menu_fade = new MenuFade()

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

// Overlay, Sneak and Settings windows: never focused, no taskbar button, and tool windows ('toolbar' sets
// WS_EX_TOOLWINDOW on Windows). skipTaskbar alone only drops the button; the shell still treats the window as an
// app window, and showing, hiding or stacking one over a borderless (Fixed Window) client can make Windows
// decide EVE is no longer the fullscreen app and bring the taskbar up over it. The shell ignores tool windows.
const OVERLAY_WINDOW = { focusable: false, skipTaskbar: true, type: 'toolbar' }

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
    if (win.__ghost) { win.__ghost_shown = true; return }   // hidden for a context menu: unghost shows it
    const pending = fades.get(win)
    if (pending) { clearTimeout(pending.delay); clearTimeout(pending.fade); fades.delete(win) }
    if (!win.isVisible()) activate ? win.show() : win.showInactive()
    win.webContents.send('visibility', true)
}

function conceal(win, { delay = 0, instant = false } = {}) {
    if (win && win.__ghost) { win.__ghost_shown = false; return }
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
// never overwrites another's on the account. Read through settings_schema.js; a save spreads the stored
// object so fields another version added survive.
function window_saved(id) {
    return read_window(settings.get(window_key(id)), window_def(id))
}

function window_enabled(id) {
    return window_saved(id).enabled
}

function save_window(id, patch) {
    settings.set(window_key(id), { ...stored_window(settings.get(window_key(id))), ...patch })
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
        ...OVERLAY_WINDOW,
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
    start_reminders()
    sync_intel()
    update_polling()
}

function set_window_enabled(id, enabled) {
    if (!window_def(id)) return
    save_window(id, { enabled })
    if (enabled) {
        hidden.delete(id)
        if (state.user && !overlays.has(id)) create_overlay(window_def(id))
        reveal_overlays()
    } else {
        destroy_overlay(id)
    }
    sync_intel()
    update_polling()   // a window enabled mid-session loads at once (it has no data yet)
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

// ---------------------------------------------------------------- fade on right-click (menu_fade.js)

// The helper reports mouse buttons only while this is on and a client is in front.
function sync_button_watch() {
    if (eve) eve.watch_buttons(!!state.user && toggle('fade_on_right_click'))
}

// Windows near the menu are hidden outright: fading only the page would leave the native glass (blur and tint)
// over the menu. While hidden, reveal/conceal only record whether the window should come back (__ghost_shown).
function ghost(win) {
    if (win.__ghost) return
    win.__ghost = true
    win.__ghost_shown = true
    win.webContents.send('visibility', false)   // so it fades back in when shown
    win.hide()
}

function unghost(win) {
    if (!win.__ghost || win.isDestroyed()) return false
    win.__ghost = false
    if (!win.__ghost_shown) return false
    reveal(win)
    return true
}

function fadeable_windows() {
    const wins = [...overlays.values()]
    if (mascot_win) wins.push(mascot_win)
    return wins.filter(win => !win.isDestroyed() && win.isVisible() && !fades.has(win))
}

menu_fade.on('fade', zone => {
    for (const win of fadeable_windows()) {
        if (intersects(zone, screen.dipToScreenRect(win, win.getBounds()))) ghost(win)
    }
})
menu_fade.on('restore', () => {
    const shown = [...overlays.values(), mascot_win].filter(win => win && unghost(win))
    if (!shown.length) return
    if (stays_with_eve()) stack_windows()
    else for (const win of shown) win.moveTop()
})

// ---------------------------------------------------------------- Sneak (opens Settings)

function ensure_mascot() {
    if (mascot_win && !mascot_win.isDestroyed()) return mascot_win
    mascot_win = base_window({
        width: 40, height: 36, ...OVERLAY_WINDOW, alwaysOnTop: true, title: 'Minmatar Fleet',
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
    const wanted = state.user && toggle('show_sneak') && !helper_starting()
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
        ...OVERLAY_WINDOW, alwaysOnTop: true,
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
            create_overlay(def)   // enabled by the account's settings: update_polling below loads it
        } else if (window_saved(def.id).bounds && !win.isDestroyed()) place(win, on_screen_bounds(window_saved(def.id).bounds, def))
    }
    update_overlay_visibility({ force: true })
    sync_intel()
    update_polling()
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
    for (const key of USER_SETTINGS) if (typeof legacy[key] === 'boolean') settings.set(key, legacy[key])
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
    if (key === 'fade_on_right_click' && !value) menu_fade.restore()
    if (key !== 'locked') update_overlay_visibility({ force: true })   // "locked" only changes the windows' drag region and grip
    update_polling()
    update_tray()
    push_state()
}

// ---------------------------------------------------------------- data

// A window's data is polled only while the window can show (poller.js window_data_wanted); otherwise
// polling would only load the API. Coming back loads at once if the data is stale.
function window_wanted(id) {
    const win = overlays.get(id)
    return window_data_wanted({
        signed_in: !!(state.user && settings),
        open: !!(win && !win.isDestroyed()),
        hidden: hidden.has(id),
        helper: eve,
    })
}

// Re-check every poller. Called whenever a window opens, closes or hides, EVE starts or stops, or the pilot changes.
function update_polling() {
    if (!fleet_window) return
    fleet_window.set_active(window_wanted('fleets'))   // the fleet views (fleet_window.js)
    for (const poller of Object.values(pollers)) poller.sync()
    if (clipboard_watch) clipboard_watch.set_active(window_wanted('intel'))
}

// The schedule feeds every Fleets tab (Upcoming, the Fleet tab's next fleet, which sign-up has formed);
// Campaigns and Intel each have their own data. Same rule for all (poller.js).
function create_pollers() {
    const poller = (id, interval_ms, run) => new Poller({ interval_ms, run, wanted: () => window_wanted(id), on_unauthorized: session_expired })
    pollers = {
        fleets: poller('fleets', config.refresh_ms, refresh_fleets),
        campaigns: poller('campaigns', config.refresh_ms, refresh_campaign),
        intel: poller('intel', INTEL_REFRESH_MS, () => intel.refresh()),
    }
}

// Every 401 from the API ends up here: the session is gone, sign out once.
function session_expired() {
    if (state.user) sign_out('Your session has expired. Sign in again.')
}

function fetch_error(err, what) {
    return err instanceof ApiError && err.status === 403
        ? `Your account does not have access to ${what}.`
        : 'Could not reach Minmatar Fleet. Retrying…'
}

// Each window's data loads on its own, so a slow campaign request never holds back the fleets list.
// A load already in flight is reused rather than started twice (poll, refresh button, enabling a window).
// Resolves true when it loaded, false when it failed (the poller backs off).
const in_flight = new Map()   // source -> promise

function load(source, fetcher, apply) {
    if (!state.user) return Promise.resolve(false)
    if (in_flight.has(source)) return in_flight.get(source)
    const done = (async () => {
        try {
            const value = await fetcher()
            if (state.user) apply(value, null)   // not if the pilot signed out meanwhile
            return true
        } catch (err) {
            diag({ t: 'refresh-error', source, status: err.status, message: err.message })
            if (!state.user) return false
            if (is_unauthorized(err)) session_expired()
            else apply(null, err)
            return false
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
        if (fleet_window) fleet_window.set_list(fleets)
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

// The refresh buttons and the tray's Refresh: every enabled window's data now, whether or not it's on
// screen. A disabled window costs no requests.
function refresh_all() {
    if (!state.user) return
    for (const [id, poller] of Object.entries(pollers)) if (window_enabled(id)) poller.poll()
    if (fleet_window) fleet_window.poll()
    check_reminders()
}

// "Remind me" toasts fire whether or not the Fleets window is up.
function check_reminders() {
    if (fleet_window && state.user) fleet_window.check_reminders()
}

function start_reminders() {
    clearInterval(reminder_timer)
    check_reminders()
    reminder_timer = setInterval(check_reminders, config.refresh_ms)
}

// ---------------------------------------------------------------- intel

// The Intel window was turned on (or off) for this pilot: give it the saved range and where the pilot is.
// Its poller (update_polling) does the fetching.
function sync_intel() {
    const on = !!state.user && window_enabled('intel')
    if (on && !intel_on) {
        const range = window_saved('intel').range
        intel.set_options({ range: range === undefined ? INTEL_DEFAULT_RANGE : range })
        intel.set_origin(state.location)
    }
    intel_on = on
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

async function verify_session() {
    const me = await api.me()
    const character = me.eve_character_profile
    state.user = {
        id: me.user_id,
        name: character ? character.character_name : me.username,
        character_id: character ? character.character_id : null,
        avatar: me.discord_user_profile ? me.discord_user_profile.avatar : null,
    }
    if (fleet_window) fleet_window.set_user(me.user_id, state.user.character_id)
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
    clearInterval(reminder_timer)
    for (const poller of Object.values(pollers)) poller.reset()
    intel_on = false
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
    sync_button_watch()
    const payload = {
        ...state,
        version: app.getVersion(),
        locked: toggle('locked'),
        settings_sync: settings.status,
        settings: Object.fromEntries(USER_SETTINGS.map(k => [k, toggle(k)])),
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
        { label: 'Refresh', enabled: signed_in, click: () => refresh_all() },
        { type: 'separator' },
        ...update_menu_items(),
        signed_in ? { label: `Sign out (${state.user.name})`, click: () => sign_out() } : { label: 'Sign in…', click: show_login },
        { label: `Quit (v${app.getVersion()})`, click: () => { quitting = true; app.quit() } },
    ]))
}

// ---------------------------------------------------------------- IPC (renderer -> main)

// The commands and the checks on their values live in ipc_commands.js (preload.js allows the same list).
const registered = new Set()
function on_command(command, handler) {
    if (!COMMANDS.includes(command)) throw new Error(`IPC command ${command} is not in ipc_commands.js`)
    registered.add(command)
    ipcMain.on(command, handler)
}

function sender_window(event) {
    return BrowserWindow.fromWebContents(event.sender)
}

on_command('login:start', () => begin_login())
on_command('login:cancel', () => login_flow && login_flow.cancel())
on_command('auth:sign-out', () => sign_out())
// The refresh button in any window's title bar refreshes every enabled window's data, like the tray's Refresh.
on_command('app:refresh', () => refresh_all())
// Fleet window clicks. Each is one click; fleet_window.js only acts on fleets, ships, killmails and
// systems it is showing, never on ids the renderer made up.
const on_fleet = (command, act) => on_command(command, (event, value) => { if (fleet_window && state.user) act(value) })
on_fleet('fleet:open', value => id_of(value) && fleet_window.open(value))
on_fleet('fleet:close', () => fleet_window.close())
on_fleet('fleet:open-site', value => id_of(value) && fleet_window.open_site(value))
on_fleet('fleet:refresh-motd', () => fleet_window.refresh_motd())
on_fleet('fleet:copy-fit', value => { const ship = fleet_ship(value); if (ship) fleet_window.copy_fit(ship.fleet_id, ship.key) })
on_fleet('fleet:sign-up', value => { const ship = fleet_ship(value); if (ship) fleet_window.sign_up(ship.fleet_id, ship.key) })
on_fleet('fleet:srp', value => id_of(value) && fleet_window.file_srp(value))
on_fleet('fleet:dismiss-loss', value => id_of(value) && fleet_window.dismiss_loss(value))
on_fleet('fleet:done', () => fleet_window.done())
on_fleet('fleet:destination', value => id_of(value) && fleet_window.set_destination(value))
on_fleet('fleet:preping', value => id_of(value) && fleet_window.preping(value))
on_fleet('fleet:start', value => id_of(value) && fleet_window.start(value))
on_fleet('fleet:remind', value => id_of(value) && fleet_window.toggle_reminder(value))
on_command('campaigns:open', () => {
    // Same rule as fleets: only a URL we built.
    if (state.campaign) shell.openExternal(state.campaign.url)
})
// Copying a d-scan or Local in EVE opens the report (clipboard_watch.js) without taking focus from EVE: the
// pilot stays in the game, and the window only takes the keyboard when they click a field (intel:focus).
// Ctrl+V in a focused window still works for anything the watch didn't recognise.
// The draft starts on the system of the client in front (EVE's logs), which the pilot can overwrite.
function start_draft(text, detected = null) {
    update_location()
    intel.set_origin(state.location)
    intel.paste(text, null, detected)
}
function on_copied(text, detected) {
    if (!intel.busy) start_draft(text, detected)
}
on_command('intel:paste-text', (event, text) => {
    clipboard_watch.mark_used(text)
    intel_typing(true)
    start_draft(text)
})
on_command('intel:focus', () => { if (intel.draft) intel_typing(true) })
on_command('intel:kind', (event, kind) => intel.set_kind(kind))
on_command('intel:edit', (event, change) => change && intel.edit_draft(change))
on_command('intel:share', async () => {
    const url = await intel.share()
    if (!url) return   // failed: the draft stays open for another try
    clipboard.writeText(url)
    intel_typing(false)
})
on_command('intel:discard', () => { intel.discard(); intel_typing(false) })
on_command('intel:open-report', (event, report_id) => intel.open_report(report_id))
on_command('intel:close-report', () => intel.close_report())
on_command('intel:copy-link', (event, report_id) => {
    const url = intel.url_for(report_id)
    if (url) clipboard.writeText(url)
})
on_command('intel:open-site', (event, report_id) => {
    const url = intel.url_for(report_id)
    if (url) shell.openExternal(url)
})
on_command('intel:range', (event, value) => {
    const range = intel_range(value)
    if (range === undefined) return
    save_window('intel', { range })
    intel.set_options({ range })
})
on_command('update:install', () => install_update())
on_command('update:download', () => { if (state.update.status === 'available') shell.openExternal(RELEASES_URL) })
on_command('update:check', () => updater && updater.check())
on_command('settings:open', () => { if (state.user) open_settings() })
on_command('settings:set', (event, change) => change && set_user_setting(change.key, change.value))
on_command('window:set-enabled', (event, value) => {
    const change = window_toggle(value)
    if (change) set_window_enabled(change.id, change.enabled)
})
on_command('lock:toggle', () => set_user_setting('locked', !toggle('locked')))
on_command('window:minimize', event => {
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
on_command('window:close', event => {
    const win = sender_window(event)
    if (win) win.close()
})
on_command('mouse:interactive', (event, interactive) => {
    const win = sender_window(event)
    if (win && (win === mascot_win || overlay_id_of(win)) && !win.isFocusable()) {
        win.setIgnoreMouseEvents(!interactive, interactive ? undefined : { forward: true })
    }
})
// Unpinned windows move by the header and resize from the grip (eve_window.js wire_drag).
let drag = null
on_command('drag:start', (event, start) => {
    const win = sender_window(event)
    if (!win || toggle('locked') || !start || !['move', 'resize'].includes(start.kind)) return
    drag = { win, kind: start.kind, point: start.point, bounds: win.getBounds(), min: window_def(overlay_id_of(win))?.min_size || { width: 320, height: 220 } }
})
on_command('drag:move', (event, point) => {
    if (!drag || drag.win.isDestroyed() || drag.win !== sender_window(event)) return
    const dx = Math.round(point.x - drag.point.x)
    const dy = Math.round(point.y - drag.point.y)
    // setBounds with the size kept, not setPosition, which can resize a window crossing monitors with different scaling.
    if (drag.kind === 'move') drag.win.setBounds({ ...drag.bounds, x: drag.bounds.x + dx, y: drag.bounds.y + dy })
    else drag.win.setBounds({ ...drag.bounds, width: Math.max(drag.min.width, drag.bounds.width + dx), height: Math.max(drag.min.height, drag.bounds.height + dy) })
})
on_command('drag:end', () => { drag = null })
for (const command of COMMANDS) if (!registered.has(command)) throw new Error(`IPC command ${command} has no handler in main.js`)

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
    api = new ApiClient({
        api_url: config.api_url,
        get_token: () => tokens.load(),
        client: client_id({ version: app.getVersion(), portable: is_portable() }),
    })
    fleet_window = new FleetWindow({
        api,
        routes: new RouteFinder(),
        web_url: config.web_url,
        clipboard,
        open_external: url => shell.openExternal(url),
        notify: (title, body) => {
            if (Notification.isSupported()) new Notification({ title, body, icon: path.join(ASSETS, 'icon.png') }).show()
        },
        // Reminders follow the account, like window positions (settings.js).
        store: { get: key => settings && settings.get(key), set: (key, value) => settings && settings.set(key, value) },
    })
    fleet_window.on('change', set_fleet_snapshot)
    fleet_window.on('unauthorized', session_expired)
    intel = new IntelController({
        api,
        web_url: config.web_url,
        on_change: view => { state.intel = view; push_state() },
        on_unauthorized: session_expired,
        diag,
    })
    clipboard_watch = new ClipboardWatch({ read: () => clipboard.readText(), on_copy: on_copied })
    create_pollers()
    settings = new Settings({
        defaults: TOGGLES,
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
        update_polling()
    })
    eve.on('change', () => {
        update_overlay_visibility()
        update_polling()
        follow_front_character()
        push_state()
    })
    eve.on('client-front', () => setTimeout(update_overlay_visibility, 300))   // EVE can land above us for a frame
    eve.on('button', event => {
        if (state.user && toggle('fade_on_right_click')) menu_fade.button(event, state.eve_window.ui_scale)
    })
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
    clearInterval(reminder_timer)
    for (const poller of Object.values(pollers)) poller.stop()
    if (clipboard_watch) clipboard_watch.set_active(false)
    if (fleet_window) fleet_window.stop()
    if (settings) settings.stop()
    if (eve) eve.stop()
    if (eve_window) eve_window.stop()
    if (eve_logs) eve_logs.stop()
    if (updater) updater.stop()
})
app.on('window-all-closed', () => {})
