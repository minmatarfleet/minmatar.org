// What the Fleets window shows when the pilot is in (or opened) a fleet, and the data behind it.
//
// One call per poll: GET /api/fleets/window/current returns the fleet the pilot commands or flies
// in, already cut down for them (the roster only for the FC). It sends an ETag, so an unchanged
// fleet costs a 304, no parse and no re-render. A fleet opened from the list adds one more call
// for that fleet. Polling follows the backend's fleet poller (30 s), stops while the window is
// closed or EVE isn't running, and backs off when the API is down.
//
// Views: list (no fleet) | fleet (FC summary, member, or form-up) | loss (your ship just died) |
// after (the FC's after-action once the fleet closes) | loading (opened, not fetched yet).
const { EventEmitter } = require('events')
const { ApiError } = require('./api')

const POLL_MS = 30_000
const MAX_BACKOFF_MS = 5 * 60_000
const COMPOSITION_TTL_MS = 5 * 60_000
const NOTICE_MS = 2500

class FleetWindow extends EventEmitter {
    constructor({ api, routes, web_url, clipboard, open_external, poll_ms = POLL_MS, now = Date.now, timers = { setTimeout, clearTimeout } }) {
        super()
        this.api = api
        this.routes = routes
        this.web_url = web_url
        this.clipboard = clipboard
        this.open_external = open_external
        this.poll_ms = poll_ms
        this.now = now
        this.timers = timers
        this.reset()
    }

    // Signed out: forget everything about this pilot.
    reset() {
        this.stop()
        this.timers.clearTimeout(this.notice_timer)
        this.active = false
        this.current = null          // window payload for the fleet the pilot is in, or null
        this.opened = null           // fleet id opened from the list
        this.opened_window = null
        this.dismissed = null        // "<fleet id>:<live>" the pilot backed out of
        this.done_losses = new Set()
        this.done_after = new Set()
        this.front = { name: null, system: null, id: null }
        this.primary_character_id = null
        this.route_key = null
        this.jumps = null
        this.notice = null
        this.busy = null
        this.error = null
        this.failures = 0
        this.last_poll = -Infinity   // never polled: the first activation polls at once
        this.loaded = false
        this.compositions = new Map()
        this.published = null
        this.polling = null
    }

    // ------------------------------------------------------------ polling

    // Poll only while the pilot can see the window. Coming back polls at once if the data is stale.
    set_active(active) {
        if (active === this.active) return
        this.active = active
        if (!active) return this.stop()
        const age = this.now() - this.last_poll
        this.schedule(age >= this.poll_ms ? 0 : this.poll_ms - age)
    }

    stop() {
        this.timers.clearTimeout(this.timer)
        this.timer = null
    }

    schedule(ms) {
        this.stop()
        this.timer = this.timers.setTimeout(() => this.poll(), ms)
    }

    poll() {
        this.stop()
        if (!this.polling) this.polling = this.fetch_windows().finally(() => { this.polling = null })
        return this.polling
    }

    async fetch_windows() {
        this.last_poll = this.now()
        let unauthorized = false
        try {
            const current = await this.api.current_fleet_window()
            this.current = current.body.window
            const opened = this.opened
            if (opened && !(this.current && this.current.fleet.id === opened)) {
                const result = await this.api.fleet_window(opened)
                if (this.opened === opened) this.opened_window = result.body
            } else {
                this.opened_window = null
            }
            this.failures = 0
            this.error = null
            this.loaded = true
        } catch (err) {
            if (err instanceof ApiError && err.status === 401) {
                unauthorized = true
                this.emit('unauthorized')
                return
            }
            if (err instanceof ApiError && (err.status === 403 || err.status === 404) && this.opened) {
                this.opened = null   // fleet deleted, or not one the pilot may see
                this.opened_window = null
            } else {
                this.failures++
                this.error = 'Could not reach Minmatar Fleet. Retrying…'
            }
        } finally {
            if (!unauthorized) {
                this.update_route()
                this.publish()
                if (this.active) this.schedule(Math.min(MAX_BACKOFF_MS, this.poll_ms * 2 ** this.failures))
            }
        }
    }

    // ------------------------------------------------------------ what to show

    shown() {
        if (this.opened) {
            if (this.current && this.current.fleet.id === this.opened) return this.current
            return this.opened_window
        }
        if (this.current && this.dismissed !== dismiss_key(this.current)) return this.current
        return null
    }

    view() {
        const win = this.shown()
        if (!win) return this.opened ? 'loading' : 'list'
        if (win.mode === 'fc' && !win.fleet.live && win.after_action && !this.done_after.has(win.fleet.id)) return 'after'
        const loss = win.me.last_loss
        if (loss && win.fleet.live && !this.done_losses.has(loss.killmail_id)) return 'loss'
        return 'fleet'
    }

    // The pilot's character in this fleet: the one whose client is in front, else the first.
    you(win) {
        const characters = (win && win.me.characters) || []
        return characters.find(c => c.character_name === this.front.name) || characters[0] || null
    }

    set_front(front) {
        const next = { name: front.name || null, system: front.system || null, id: front.id || null }
        if (JSON.stringify(next) === JSON.stringify(this.front)) return
        this.front = next
        this.update_route()
        this.publish()
    }

    set_primary_character(character_id) {
        this.primary_character_id = character_id || null
    }

    // Jumps from the pilot to the fleet (live) or the form-up (not started). The pilot's own
    // client's Local log beats the backend's 30 s old fleet poll when it is the same character.
    update_route() {
        const win = this.shown()
        if (!win || win.mode === 'fc') return this.set_route(null)
        const you = this.you(win)
        const destination = win.fleet.live ? win.fleet.fc_system_id : win.fleet.location_system_id
        let origin = this.front.system
        if (you && !(this.front.name === you.character_name && this.front.system)) origin = you.solar_system_id
        if (!origin || !destination) return this.set_route(null)
        const key = `${origin}>${destination}`
        if (key === this.route_key) return
        this.route_key = key
        this.jumps = null
        this.routes.jumps(origin, destination).then(jumps => {
            if (this.route_key !== key) return
            this.jumps = jumps
            this.publish()
        })
    }

    set_route(key) {
        this.route_key = key
        this.jumps = null
    }

    snapshot() {
        const view = this.view()
        const win = this.shown()
        if (!win) return { view, error: this.error, loaded: this.loaded }
        const you = this.you(win)
        const sign_up_character = this.sign_up_character(win)
        return {
            view,
            mode: win.mode,
            opened: !!this.opened,
            fleet: win.fleet,
            counts: win.counts,
            ships: win.ships,
            roles: win.roles,
            needs: win.needs,
            pilots: win.pilots,
            attention: win.attention,
            after_action: win.after_action,
            loss: win.me.last_loss,
            you,
            signed_up_key: sign_up_character ? (win.me.ship_volunteers[sign_up_character] || null) : null,
            jumps: this.jumps,
            front_name: this.front.name,
            notice: this.notice,
            busy: this.busy,
            error: this.error,
        }
    }

    // Emit only when something the window draws changed (the timer and focus changes don't count).
    publish() {
        const snapshot = this.snapshot()
        const signature = JSON.stringify(snapshot)
        if (signature === this.published) return
        this.published = signature
        this.emit('change', snapshot)
    }

    // ------------------------------------------------------------ actions (each one a pilot's click)

    open(fleet_id) {
        if (!Number.isInteger(fleet_id)) return
        this.opened = fleet_id
        this.opened_window = null
        this.update_route()
        this.publish()
        return this.poll()
    }

    back() {
        if (this.opened) {
            this.opened = null
            this.opened_window = null
        } else if (this.current) {
            this.dismissed = dismiss_key(this.current)
        }
        this.update_route()
        this.publish()
    }

    dismiss_loss() {
        const win = this.shown()
        if (win && win.me.last_loss) this.done_losses.add(win.me.last_loss.killmail_id)
        this.publish()
    }

    done() {
        const win = this.shown()
        if (win) this.done_after.add(win.fleet.id)
        this.back()
    }

    open_site() {
        const win = this.shown()
        if (win) this.open_external(`${this.web_url}/fleets/upcoming/${win.fleet.id}`)
    }

    // The killmail link goes on the clipboard and the SRP page opens: paste it into the request.
    file_srp() {
        const win = this.shown()
        const loss = win && win.me.last_loss
        if (!loss) return
        this.clipboard.writeText(`https://zkillboard.com/kill/${loss.killmail_id}/`)
        this.open_external(`${this.web_url}/ships/srp/killmails/`)
        this.flash('Killmail link copied')
    }

    async copy_fit(key) {
        const win = this.shown()
        if (!win) return
        try {
            const entry = (await this.composition(win.fleet.id)).find(e => e.key === key)
            if (!entry || !entry.eft_format) return this.flash('Fit not found')
            this.clipboard.writeText(entry.eft_format)
            this.flash('Fit copied')
        } catch (err) {
            this.flash('Could not load the fit')
        }
    }

    async composition(fleet_id) {
        const cached = this.compositions.get(fleet_id)
        if (cached && this.now() - cached.at < COMPOSITION_TTL_MS) return cached.entries
        const entries = await this.api.fleet_composition(fleet_id)
        this.compositions.set(fleet_id, { entries, at: this.now() })
        return entries
    }

    // Sign up with the character whose client is in front when it is one of the pilot's, else their main.
    sign_up_character(win) {
        const you = this.you(win)
        if (you) return you.character_id
        const mine = new Set(win.me.character_ids || [])
        if (this.front.id && mine.has(this.front.id)) return this.front.id
        return this.primary_character_id && mine.has(this.primary_character_id) ? this.primary_character_id : (win.me.character_ids || [])[0] || null
    }

    async sign_up(key) {
        const win = this.shown()
        if (!win || this.busy || !win.ships.some(s => s.key === key)) return
        const character_id = this.sign_up_character(win)
        if (!character_id) return this.flash('No character to sign up')
        this.busy = 'sign-up'
        this.publish()
        try {
            await this.api.set_my_ship(win.fleet.id, character_id, key)
            this.flash('Signed up')
        } catch (err) {
            this.flash(err.status === 400 ? 'That ship is not in this fleet any more' : 'Could not sign up. Try again.')
        } finally {
            this.busy = null
            this.publish()
        }
        return this.poll()
    }

    async refresh_motd() {
        const win = this.shown()
        if (!win || win.mode !== 'fc' || !win.fleet.live || this.busy) return
        this.busy = 'motd'
        this.publish()
        try {
            await this.api.refresh_motd(win.fleet.id)
            this.flash('MOTD refreshed')
        } catch (err) {
            this.flash('Could not refresh the MOTD')
        } finally {
            this.busy = null
            this.publish()
        }
    }

    flash(message) {
        this.notice = message
        this.publish()
        this.timers.clearTimeout(this.notice_timer)
        this.notice_timer = this.timers.setTimeout(() => {
            this.notice = null
            this.publish()
        }, NOTICE_MS)
    }
}

function dismiss_key(win) {
    return `${win.fleet.id}:${win.fleet.live}`
}

module.exports = { FleetWindow, POLL_MS, MAX_BACKOFF_MS }
