// Pilot settings (window positions, toggles) saved on the API under the signed-in user, so they follow
// the pilot to any PC and nothing but the session token is kept on disk.
//
// The API being down never blocks or breaks the app:
//   - until the account's copy loads, the app runs on defaults, and load() keeps retrying in the background
//   - changes apply at once in memory and are sent as a merge (only the keys that changed), retried with
//     backoff until the API takes them
//   - when the account's copy arrives late, keys changed here in the meantime win; the rest are applied
//     and announced with a 'change' event so windows can move to where the pilot left them
//
// Session keys live in memory only and never reach the API (e.g. "pinned", which resets every launch).
const { EventEmitter } = require('events')

const SAVE_DELAY_MS = 1000
const RETRY_MS = [2_000, 5_000, 15_000, 30_000, 60_000]

// 401/403: signed out or not allowed, the sign-out flow handles it. 400: the API rejected the values,
// sending them again won't help. Everything else (offline, timeouts, 5xx, 429) is worth retrying.
function retryable(err) {
    return ![400, 401, 403].includes(err && err.status)
}

const same = (a, b) => JSON.stringify(a) === JSON.stringify(b)

class Settings extends EventEmitter {
    constructor({ defaults, session_keys = [], remote, save_delay_ms = SAVE_DELAY_MS, retry_ms = RETRY_MS }) {
        super()
        this.defaults = { ...defaults }
        this.session_keys = new Set(session_keys)
        this.remote = remote   // { load(): Promise<{ values }>, save(values): Promise }
        this.save_delay_ms = save_delay_ms
        this.retry_ms = retry_ms
        this.generation = 0
        this.reset()
    }

    // Back to defaults with nothing pending: at sign-out, so the next pilot never sees or sends this one's settings.
    reset() {
        this.stop()
        this.generation++
        this.values = { ...this.defaults }
        this.pending = new Map()      // key -> change number, for keys set here and not saved yet
        this.change_number = 0
        this.loaded = false
        this.saving = null
        this.load_attempt = 0
        this.save_attempt = 0
        this.status = 'local'         // local (account copy not loaded) | synced | saving | offline
    }

    get(key) {
        return this.values[key]
    }

    set(key, value) {
        // Before the account's copy loads, even a "no change" is the pilot's choice and must win over it.
        if (same(this.values[key], value) && (this.loaded || this.session_keys.has(key))) return
        this.values[key] = value
        if (this.session_keys.has(key)) return
        this.pending.set(key, ++this.change_number)
        this.schedule_save(this.save_delay_ms)
    }

    // Fetch the account's copy. Resolves true once applied; on failure resolves false and retries in the background.
    async load() {
        clearTimeout(this.load_timer)
        const generation = this.generation
        let remote
        try {
            remote = await this.remote.load()
        } catch (err) {
            if (generation !== this.generation) return false
            this.emit('error', { op: 'load', status: err.status, message: err.message })
            if (retryable(err)) {
                this.set_status('offline')
                this.load_timer = setTimeout(() => this.load(), this.backoff(this.load_attempt++))
            }
            return false
        }
        if (generation !== this.generation) return false
        this.load_attempt = 0
        this.loaded = true
        const remote_values = (remote && remote.values) || {}
        this.emit('loaded', remote_values)
        const changed = this.merge(remote_values)
        this.set_status(this.pending.size ? 'saving' : 'synced')
        if (changed.length) this.emit('change', changed)
        return true
    }

    // Send pending changes now. Resolves true when nothing is left to send.
    async flush() {
        clearTimeout(this.save_timer)
        while (this.saving) await this.saving
        if (!this.pending.size) return true
        const generation = this.generation
        const sent = new Map(this.pending)
        const values = Object.fromEntries([...sent.keys()].map(k => [k, this.values[k] === undefined ? null : this.values[k]]))
        const drop_sent = () => { for (const [key, n] of sent) if (this.pending.get(key) === n) this.pending.delete(key) }
        this.set_status('saving')
        const saving = this.remote.save(values)
            .then(() => {
                if (generation !== this.generation) return
                drop_sent()   // keys changed again while the request was in flight stay pending
                this.save_attempt = 0
                this.emit('saved', values)
                if (this.pending.size) this.schedule_save(0)
                else this.set_status(this.loaded ? 'synced' : 'local')
            })
            .catch(err => {
                if (generation !== this.generation) return
                this.emit('error', { op: 'save', status: err.status, message: err.message })
                if (retryable(err)) {
                    this.set_status('offline')
                    this.schedule_save(this.backoff(this.save_attempt++))
                } else {
                    drop_sent()
                    this.set_status(this.loaded ? 'synced' : 'local')
                }
            })
            .finally(() => { if (this.saving === saving) this.saving = null })   // a reset may have started another
        this.saving = saving
        await saving
        return generation === this.generation && !this.pending.size
    }

    has_pending() {
        return this.pending.size > 0
    }

    stop() {
        clearTimeout(this.save_timer)
        clearTimeout(this.load_timer)
    }

    // ---------------------------------------------------------------- internals

    merge(remote_values) {
        const changed = []
        const keys = new Set([...Object.keys(this.defaults), ...Object.keys(remote_values)])
        for (const key of keys) {
            if (this.session_keys.has(key) || this.pending.has(key)) continue
            const next = key in remote_values ? remote_values[key] : this.defaults[key]
            if (!same(this.values[key], next)) {
                this.values[key] = next
                changed.push(key)
            }
        }
        return changed
    }

    schedule_save(ms) {
        clearTimeout(this.save_timer)
        this.save_timer = setTimeout(() => this.flush(), ms)
    }

    backoff(attempt) {
        return this.retry_ms[Math.min(attempt, this.retry_ms.length - 1)]
    }

    set_status(status) {
        if (status === this.status) return
        this.status = status
        this.emit('status', status)
    }
}

module.exports = { Settings }
