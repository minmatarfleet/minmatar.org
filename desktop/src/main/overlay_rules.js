// When the pinned overlay should be on screen.
//
// "Only over EVE" (default): visible while a logged-in EVE client or this app is in front, hidden when
// another app takes over (so it doesn't float over your browser). Some windows that come to the
// front aren't "another app" and must not hide it:
//   - screenshot tools: Win+Shift+S / Snipping Tool, ShareX, Greenshot, Lightshot. They take the
//     foreground just before capturing, so hiding would cut the overlay out of every screenshot.
//   - Windows shell surfaces: taskbar, Alt+Tab, Start, search, notification centre.
// A client still at character select (window title "EVE", not "EVE - <Character>") doesn't count.
// "Over everything": always visible while pinned.

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

function is_passthrough_window(foreground) {
    const proc = (foreground.proc || '').toLowerCase()
    if (CAPTURE_PROCS.has(proc) || SHELL_PROCS.has(proc)) return true
    return proc === 'explorer' && EXPLORER_SHELL_CLASSES.has(foreground.cls || '')
}

// Returns true (show), false (hide) or null (no opinion: keep whatever is showing now).
function overlay_should_show({ helper_ready, eve_running, foreground, own_pids, only_over_eve }) {
    if (!only_over_eve || !helper_ready || !eve_running) return true
    if (!foreground || foreground.hwnd === '0') return null      // focus is mid-switch; wait for the next window
    if (foreground.client) return is_logged_in_client(foreground)
    if (own_pids.has(foreground.pid)) return true
    if (is_passthrough_window(foreground)) return null
    return false
}

// Sneak follows the last logged-in client that was in front and sits on its notification badge. Unlike
// the overlay windows he never shows over other apps, and never without a client to sit on.
function mascot_should_show({ helper_ready, foreground, own_pids, active_client }) {
    if (!helper_ready || !active_client || active_client.min) return false
    if (!foreground || foreground.hwnd === '0') return null
    if (foreground.client) return is_logged_in_client(foreground)
    if (own_pids.has(foreground.pid)) return true
    if (is_passthrough_window(foreground)) return null
    return false
}

// Switching to an EVE client that isn't logged in: hide at once (no delay, no fade). Even a short fade
// leaves the overlay visibly sitting on the login screen. Other apps get the short fade.
function hide_instantly(foreground) {
    return !!(foreground && foreground.client && !is_logged_in_client(foreground))
}

module.exports = { overlay_should_show, mascot_should_show, is_passthrough_window, is_logged_in_client, hide_instantly }
