// The overlay windows the app offers. Settings lists these so pilots choose which ones they use.
// Add a window here (plus its page in src/renderer/) and it shows up in Settings automatically.
const OVERLAY_WINDOWS = [
    {
        id: 'fleets',
        title: 'Upcoming Fleets',
        description: 'Upcoming and live fleets with EVE-time starts and countdowns.',
        page: 'fleets.html',
        size: { width: 380, height: 520 },
        min_size: { width: 320, height: 220 },
        default_enabled: true,
    },
]

function window_def(id) {
    return OVERLAY_WINDOWS.find(w => w.id === id) || null
}

module.exports = { OVERLAY_WINDOWS, window_def }
