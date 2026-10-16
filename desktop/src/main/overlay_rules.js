// When the pinned overlay should be on screen.
//
// "Stay with EVE" (default; saved as only_over_eve): the windows sit directly on top of the EVE client in
// the window order instead of above every app (main.js stacks them there), so another app brought in
// front of EVE (Discord, a browser) covers them just as it covers EVE. They stay up while that client is
// on screen underneath, and hide when it's minimised, closed or back at character select.
// A client still at character select (window title "EVE", not "EVE - <Character>") doesn't count.
// Some windows that come to the front keep whatever is showing:
//   - screenshot tools: Win+Shift+S / Snipping Tool, ShareX, Greenshot, Lightshot. They take the
//     foreground just before capturing, so hiding would cut the overlay out of every screenshot.
//   - Windows shell surfaces: taskbar, Alt+Tab, Start, search, notification centre.
// "Over everything": always visible while pinned, above every app.

const CAPTURE_PROCS = new Set([
    'screenclippinghost', 'snippingtool', 'screensketch',
    'sharex', 'greenshot', 'lightshot', 'flameshot',
])
const SHELL_PROCS = new Set([
    'startmenuexperiencehost', 'searchhost', 'searchapp', 'shellexperiencehost', 'shellhost',
])
// explorer.exe also owns the desktop and File Explorer windows, so only its shell classes count.
const EXPLORER_SHELL_CLASSES = new Set([
    'Shell_TrayWnd', 'Shell_SecondaryTrayWnd', 'MultitaskingViewFrame', 'XamlExplorerHostIslandWindow',
    'ForegroundStaging', 'TaskListThumbnailWnd', 'NotifyIconOverflowWindow', 'TopLevelWindowForOverflowXamlIsland',
])

function is_logged_in_client(foreground) {
    return !!foreground.client && /^EVE - \S/.test(foreground.title || '')
}

// An EVE client from the helper's client list that is logged in and not minimised.
function client_on_screen(client) {
    return !!client && !client.min && /^EVE - \S/.test(client.title || '')
}

function is_passthrough_window(foreground) {
    const proc = (foreground.proc || '').toLowerCase()
    if (CAPTURE_PROCS.has(proc) || SHELL_PROCS.has(proc)) return true
    return proc === 'explorer' && EXPLORER_SHELL_CLASSES.has(foreground.cls || '')
}

// Returns true (show), false (hide) or null (no opinion: keep whatever is showing now).
// active_client: the client the windows sit on (the last logged-in client in front).
function overlay_should_show({ helper_ready, eve_running, foreground, own_pids, stay_with_eve, active_client }) {
    if (!stay_with_eve || !helper_ready || !eve_running) return true
    if (!foreground || foreground.hwnd === '0') return null      // focus is mid-switch; wait for the next window
    if (foreground.client) return is_logged_in_client(foreground)
    if (own_pids.has(foreground.pid)) return true
    if (is_passthrough_window(foreground)) return null
    return client_on_screen(active_client)   // another app in front: stay on EVE underneath it
}

// Sneak follows the last logged-in client that was in front and sits on its notification badge, never
// without a client to sit on. With "Stay with EVE" he stays on that client under other apps, like the
// windows; otherwise he never shows over other apps.
function mascot_should_show({ helper_ready, foreground, own_pids, active_client, stay_with_eve }) {
    if (!helper_ready || !active_client || active_client.min) return false
    if (!foreground || foreground.hwnd === '0') return null
    if (foreground.client) return is_logged_in_client(foreground)
    if (own_pids.has(foreground.pid)) return true
    if (is_passthrough_window(foreground)) return null
    return !!stay_with_eve && client_on_screen(active_client)
}

// Switching to an EVE client that isn't logged in: hide at once (no delay, no fade). Even a short fade
// leaves the overlay visibly sitting on the login screen. Other apps get the short fade.
function hide_instantly(foreground) {
    return !!(foreground && foreground.client && !is_logged_in_client(foreground))
}

module.exports = { overlay_should_show, mascot_should_show, is_passthrough_window, is_logged_in_client, client_on_screen, hide_instantly }
