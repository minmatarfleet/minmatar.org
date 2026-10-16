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
    {
        id: 'campaigns',
        title: 'Campaigns',
        description: 'Your live campaign: whether each system is gaining or losing, and who flew in the last hour.',
        page: 'campaigns.html',
        size: { width: 420, height: 340 },
        min_size: { width: 300, height: 220 },
        default_enabled: false,
    },
]

function window_def(id) {
    return OVERLAY_WINDOWS.find(w => w.id === id) || null
}

module.exports = { OVERLAY_WINDOWS, window_def }
