// One polling policy for every window's data (the fleet list, the fleet view, Campaigns and Intel):
//   - it runs only while wanted(): main.js wants a window's data while the window is open (enabled, not
//     closed to the tray) and EVE is running, because the window can't show otherwise
//   - when it becomes wanted again it fetches at once if the data is older than one interval, so a window
//     never comes back stale; otherwise it waits out the rest of the interval
//   - a failed run backs off (interval x 2, x 4, ... up to MAX_BACKOFF_MS) and a good one resets it
//   - a 401 hands over to on_unauthorized (sign-out) and stops: no retry with a dead session
//   - poll() runs now whether or not it is wanted (the refresh buttons, the tray's Refresh, a click)
// run() resolves false (or throws) when it failed; anything else is a success.
const { is_unauthorized } = require('./api')

const MAX_BACKOFF_MS = 5 * 60_000

// main.js's wanted() rule for a window's data: signed in, the window open (enabled, not closed or minimised
// to the tray), and EVE running. Without the helper (not Windows, PowerShell blocked) the app can't tell
// whether EVE runs and the windows float over everything, so the data is wanted.
function window_data_wanted({ signed_in, open, hidden, helper }) {
    if (!signed_in || !open || hidden) return false
    return !helper || !helper.supported || !!helper.failed || !!helper.eve_running
}

class Poller {
    constructor({ interval_ms, run, wanted = () => true, on_unauthorized = () => {}, max_backoff_ms = MAX_BACKOFF_MS, now = Date.now, timers = { setTimeout, clearTimeout } }) {
        this.interval_ms = interval_ms
        this.run = run
        this.wanted = wanted
        this.on_unauthorized = on_unauthorized
        this.max_backoff_ms = max_backoff_ms
        this.now = now
        this.timers = timers
        this.timer = null
        this.generation = 0
        this.reset()
    }

    // Forget the last run (sign-out): the next pilot's data loads as soon as it is wanted.
    reset() {
        this.cancel()
        this.generation++   // a run still in flight finishes without touching the next pilot's schedule
        this.active = false
        this.last_run = -Infinity
        this.failures = 0
        this.running = null
    }

    // Re-check wanted(). Call it whenever something it depends on may have changed.
    sync() {
        this.set_active(!!this.wanted())
    }

    set_active(active) {
        if (active === this.active) return
        this.active = active
        if (!active) return this.cancel()
        const age = this.now() - this.last_run
        this.schedule(age >= this.interval_ms ? 0 : this.interval_ms - age)
    }

    stop() {
        this.active = false
        this.cancel()
    }

    cancel() {
        this.timers.clearTimeout(this.timer)
        this.timer = null
    }

    schedule(ms) {
        this.cancel()
        this.timer = this.timers.setTimeout(() => this.poll(), ms)
    }

    // Run now (or join the run in flight). Resolves when it is done.
    poll() {
        this.cancel()
        if (!this.running) {
            const running = this.tick().finally(() => { if (this.running === running) this.running = null })
            this.running = running
        }
        return this.running
    }

    // How long until the next run: the interval, doubled for each failure in a row, capped.
    delay() {
        return Math.min(this.max_backoff_ms, this.interval_ms * 2 ** this.failures)
    }

    async tick() {
        const generation = this.generation
        this.last_run = this.now()
        let ok = false
        try {
            ok = (await this.run()) !== false
        } catch (err) {
            if (generation !== this.generation) return
            if (is_unauthorized(err)) {
                this.stop()
                this.on_unauthorized(err)
                return
            }
        }
        if (generation !== this.generation) return
        this.failures = ok ? 0 : this.failures + 1
        if (this.active) this.schedule(this.delay())
    }
}

module.exports = { Poller, window_data_wanted, MAX_BACKOFF_MS }
