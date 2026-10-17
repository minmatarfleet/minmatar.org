// The data behind the Fleets window's three tabs: Fleet (the fleet you are in, or the next one that
// matters to you), Upcoming (the schedule, and one fleet opened from it) and Recent (your last fleets and
// any SRP you still owe). The renderer owns which tab is showing; nothing here ever hides the fleet you
// are in, so there is no "dismissed" state to get stuck in.
//
// One call per poll for the fleet you are in: GET /api/fleets/window/current, already cut down for you
// (the roster and kill feed only for the FC). A fleet opened from the schedule, your live sign-up you
// haven't joined, or the fleet you FC next each add one /{id}/window call. All send ETags, so an
// unchanged fleet costs a 304 and no re-render. Recent and your sign-ups come from /window/mine every
// two minutes. Polling stops while the window is closed or EVE isn't running, and backs off when the API
// is down.
const { EventEmitter } = require('events')
const { ApiError } = require('./api')

const POLL_MS = 30_000
const MINE_POLL_MS = 120_000
const MAX_BACKOFF_MS = 5 * 60_000
const COMPOSITION_TTL_MS = 5 * 60_000
const NOTICE_MS = 2500
// Your own fleet shows its pre-flight on the Fleet tab this long before its start time.
const PREP_WINDOW_MS = 3 * 3600_000
// "Remind me" fires this long before form-up, and not at all once the fleet is this far past its start.
const REMIND_BEFORE_MS = 15 * 60_000
const REMIND_LATE_MS = 10 * 60_000
const REMINDERS_KEY = 'fleet_reminders'

class FleetWindow extends EventEmitter {
    constructor({
        api, routes, web_url, clipboard, open_external,
        notify = () => {}, store = null,
        poll_ms = POLL_MS, mine_poll_ms = MINE_POLL_MS, now = Date.now, timers = { setTimeout, clearTimeout },
    }) {
        super()
        this.api = api
        this.routes = routes
        this.web_url = web_url
        this.clipboard = clipboard
        this.open_external = open_external
        this.notify = notify
        this.store = store   // { get(key), set(key, value) }: the account's desktop settings (reminders)
        this.poll_ms = poll_ms
        this.mine_poll_ms = mine_poll_ms
        this.now = now
        this.timers = timers
        this.reset()
    }

    // Signed out: forget everything about this pilot.
    reset() {
        this.stop()
        this.timers.clearTimeout(this.notice_timer)
        this.active = false
        this.current = null           // window payload for the fleet you are in (or just ran), or null
        this.windows = new Map()      // fleet id -> window payload for the other fleets on screen
        this.opened = null            // fleet id opened from the schedule
        this.list = []                // the schedule (api.js load_upcoming_fleets rows)
        this.user_id = null
        this.primary_character_id = null
        this.mine = null              // /window/mine: { fleets, srp_owed, signups }
        this.mine_at = -Infinity
        this.done_losses = new Set()  // loss cards closed (their SRP stays in Recent)
        this.done_after = new Set()   // wrap-ups marked done
        this.prepinged = new Set()    // fleets pre-pinged from here this session
        this.reminded = new Set()
        this.front = { name: null, system: null, id: null }
        this.routes_known = new Map() // "origin>destination" -> jumps
        this.routes_asked = new Set()
        this.notice = null
        this.busy = null
        this.error = null
        this.failures = 0
        this.last_poll = -Infinity    // never polled: the first activation polls at once
        this.synced_at = null
        this.loaded = false
        this.compositions = new Map()
        this.published = null
        this.polling = null
    }

    // ------------------------------------------------------------ inputs from main.js

    set_user(user_id, primary_character_id) {
        this.user_id = user_id || null
        this.primary_character_id = primary_character_id || null
    }

    set_primary_character(character_id) {
        this.primary_character_id = character_id || null
    }

    // The schedule changed: the Fleet tab may now want another fleet (a sign-up went live, your own fleet
    // is close). Fetch it now rather than at the next poll.
    set_list(fleets) {
        this.list = Array.isArray(fleets) ? fleets : []
        const missing = this.watched().some(id => !this.windows.has(id))
        this.publish()
        if (missing && this.active && this.loaded) this.schedule(0)
    }

    set_front(front) {
        const next = { name: front.name || null, system: front.system || null, id: front.id || null }
        if (JSON.stringify(next) === JSON.stringify(this.front)) return
        this.front = next
        this.publish()
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
        if (!this.polling) this.polling = this.fetch_all().finally(() => { this.polling = null })
        return this.polling
    }

    async fetch_all() {
        this.last_poll = this.now()
        let unauthorized = false
        try {
            const current = await this.api.current_fleet_window()
            this.current = current.body.window
            if (this.now() - this.mine_at >= this.mine_poll_ms) await this.fetch_mine()
            await this.fetch_watched()
            this.failures = 0
            this.error = null
            this.loaded = true
            this.synced_at = new Date(this.now()).toISOString()
        } catch (err) {
            if (err instanceof ApiError && err.status === 401) {
                unauthorized = true
                this.emit('unauthorized')
                return
            }
            this.failures++
            this.error = 'Could not reach Minmatar Fleet. Retrying…'
        } finally {
            if (!unauthorized) {
                this.publish()
                if (this.active) this.schedule(Math.min(MAX_BACKOFF_MS, this.poll_ms * 2 ** this.failures))
            }
        }
    }

    // Recent and sign-ups are a nice-to-have on every tab: a failure here never fails the poll.
    async fetch_mine() {
        this.mine_at = this.now()
        try {
            this.mine = (await this.api.my_fleets()).body
        } catch (err) {
            if (err instanceof ApiError && err.status === 401) throw err
        }
    }

    async fetch_watched() {
        const ids = this.watched()
        for (const id of [...this.windows.keys()]) if (!ids.includes(id)) this.windows.delete(id)
        for (const id of ids) {
            try {
                this.windows.set(id, (await this.api.fleet_window(id)).body)
            } catch (err) {
                if (!(err instanceof ApiError) || ![403, 404].includes(err.status)) throw err
                this.windows.delete(id)   // fleet deleted, or not one the pilot may see
                if (this.opened === id) this.opened = null
            }
        }
    }

    // Fleets other than the one you are in that need their window fetched.
    watched() {
        const ids = []
        const focus = this.focus()
        if (['formup', 'prep'].includes(focus.kind)) ids.push(focus.id)
        const opened_is_current = this.current && this.current.fleet.id === this.opened
        if (this.opened && !opened_is_current && !ids.includes(this.opened)) ids.push(this.opened)
        return ids
    }

    // ------------------------------------------------------------ what the Fleet tab shows

    signups() {
        const by_fleet = {}
        for (const s of (this.mine && this.mine.signups) || []) if (!by_fleet[s.fleet_id]) by_fleet[s.fleet_id] = s
        return by_fleet
    }

    // The fleet you are in, or the FC's fleet that just ended until its wrap-up is done.
    current_shown() {
        const win = this.current
        if (!win) return null
        if (win.fleet.live) return win
        if (win.mode === 'fc' && win.after_action && !this.done_after.has(win.fleet.id)) return win
        return null
    }

    // In order: the fleet you are in; your sign-up that has formed without you; the fleet you FC next
    // (pre-flight, within 3 h); else just the next fleet (yours first).
    focus() {
        const current = this.current_shown()
        if (current) return { kind: current.fleet.live ? 'current' : 'wrapup', id: current.fleet.id }
        const signed = this.signups()
        const open = this.list.filter(f => f.status !== 'cancelled')
        const formed = open.find(f => f.live && signed[f.id])
        if (formed) return { kind: 'formup', id: formed.id }
        const now = this.now()
        const mine = open.find(f => !f.live && this.user_id && f.fc_user_id === this.user_id
            && new Date(f.start_time) - now <= PREP_WINDOW_MS)
        if (mine) return { kind: 'prep', id: mine.id }
        const next = this.next_fleet()
        return next ? { kind: 'next', id: next.id } : { kind: 'none', id: null }
    }

    next_fleet() {
        const signed = this.signups()
        const upcoming = this.list.filter(f => !f.live && f.status !== 'cancelled')
        return upcoming.find(f => signed[f.id]) || upcoming[0] || null
    }

    // The pilot's character in this fleet: the one whose client is in front, else the first.
    you(win) {
        const characters = (win && win.me.characters) || []
        return characters.find(c => c.character_name === this.front.name) || characters[0] || null
    }

    // The character a click acts as: yours in the fleet, else the client in front when it is one of
    // yours, else your main.
    acting_character(win) {
        const mine = new Set(win.me.character_ids || [])
        const you = this.you(win)
        if (you) return you.character_id
        if (this.front.id && mine.has(this.front.id)) return this.front.id
        if (this.primary_character_id && mine.has(this.primary_character_id)) return this.primary_character_id
        return (win.me.character_ids || [])[0] || null
    }

    // Jumps from you to the fleet (live) or its form-up. Your own client's Local log beats the backend's
    // 30 s old fleet poll when it is the same character. Looked up once per origin and destination.
    jumps(win) {
        const you = this.you(win)
        const destination = win.fleet.live ? win.fleet.fc_system_id : win.fleet.location_system_id
        let origin = this.front.system
        if (you && !(this.front.name === you.character_name && this.front.system)) origin = you.solar_system_id
        if (!origin || !destination) return null
        const key = `${origin}>${destination}`
        if (this.routes_known.has(key)) return this.routes_known.get(key)
        if (!this.routes_asked.has(key)) {
            this.routes_asked.add(key)
            this.routes.jumps(origin, destination).then(jumps => {
                this.routes_known.set(key, jumps)
                this.publish()
            })
        }
        return null
    }

    reminders() {
        const list = this.store && this.store.get(REMINDERS_KEY)
        return Array.isArray(list) ? list.filter(r => r && Number.isInteger(r.id)) : []
    }

    view_of(win) {
        if (!win) return null
        const last = win.me.last_loss
        const signed_character = this.acting_character(win)
        return {
            mode: win.mode,
            fleet: win.fleet,
            counts: win.counts,
            ships: win.ships,
            roles: win.roles,
            needs: win.needs,
            pilots: win.pilots,
            attention: win.attention,
            after_action: win.after_action,
            feed: win.feed || [],
            loss: last && !this.done_losses.has(last.killmail_id) ? last : null,
            you: this.you(win),
            signed_up_key: signed_character ? (win.me.ship_volunteers[signed_character] || null) : null,
            jumps: win.mode === 'fc' ? null : this.jumps(win),
            prepinged: this.prepinged.has(win.fleet.id),
            reminder: this.reminders().some(r => r.id === win.fleet.id),
        }
    }

    snapshot() {
        const focus = this.focus()
        const current = this.current_shown()
        const live = current && current.fleet.live ? this.view_of(current) : null
        const focus_win = ['current', 'wrapup'].includes(focus.kind) ? current
            : ['formup', 'prep'].includes(focus.kind) ? this.windows.get(focus.id) : null
        const opened_is_current = !!(this.current && this.current.fleet.id === this.opened)
        return {
            loaded: this.loaded,
            error: this.error,
            notice: this.notice,
            busy: this.busy,
            synced_at: this.synced_at,
            focus: { kind: focus.kind, id: focus.id, fleet: this.view_of(focus_win) },
            next: this.next_fleet(),
            live: live && {
                id: live.fleet.id, title: live.fleet.title, started_at: live.fleet.started_at,
                mode: live.mode, you: live.you, jumps: live.jumps,
            },
            opened: this.opened ? {
                id: this.opened,
                is_current: opened_is_current && this.current.fleet.live,
                row: this.list.find(f => f.id === this.opened) || null,
                fleet: this.view_of(opened_is_current ? this.current : this.windows.get(this.opened)),
            } : null,
            recent: this.mine ? { fleets: this.mine.fleets, srp_owed: this.mine.srp_owed } : null,
            signups: this.signups(),
            reminders: this.reminders().map(r => r.id),
        }
    }

    // Emit only when something the window draws changed (focus changes that move nothing don't count).
    // The sync time is drawn, so a poll emits; the renderer only rewrites the parts whose HTML changed.
    publish() {
        const snapshot = this.snapshot()
        const signature = JSON.stringify(snapshot)
        if (signature === this.published) return
        this.published = signature
        this.emit('change', snapshot)
    }

    // ------------------------------------------------------------ lookups for clicks

    // Every fleet window this module holds, by id. Clicks may only name these.
    known_window(fleet_id) {
        if (this.current && this.current.fleet.id === fleet_id) return this.current
        return this.windows.get(fleet_id) || null
    }

    known_fleet_id(fleet_id) {
        return !!(this.known_window(fleet_id) || this.list.some(f => f.id === fleet_id)
            || ((this.mine && this.mine.fleets) || []).some(f => f.fleet_id === fleet_id))
    }

    known_loss(killmail_id) {
        const windows = [this.current, ...this.windows.values()].filter(Boolean)
        if (windows.some(w => w.me.last_loss && w.me.last_loss.killmail_id === killmail_id)) return true
        return ((this.mine && this.mine.fleets) || []).some(f => f.my_losses.some(l => l.killmail_id === killmail_id))
    }

    // ------------------------------------------------------------ actions (each one a pilot's click)

    open(fleet_id) {
        if (!Number.isInteger(fleet_id) || !this.list.some(f => f.id === fleet_id)) return
        this.opened = fleet_id
        this.publish()
        return this.poll()
    }

    close() {
        if (!this.opened) return
        this.opened = null
        this.publish()
    }

    dismiss_loss(killmail_id) {
        if (!Number.isInteger(killmail_id)) return
        this.done_losses.add(killmail_id)
        this.mine_at = -Infinity   // the loss now lives in Recent: make sure it's there
        this.publish()
        if (this.active) this.schedule(0)
    }

    done() {
        const win = this.current_shown()
        if (!win || win.fleet.live) return
        this.done_after.add(win.fleet.id)
        this.mine_at = -Infinity
        this.publish()
        if (this.active) this.schedule(0)
    }

    open_site(fleet_id) {
        if (!Number.isInteger(fleet_id) || !this.known_fleet_id(fleet_id)) return
        const ended = ((this.mine && this.mine.fleets) || []).find(f => f.fleet_id === fleet_id && !f.live)
        this.open_external(`${this.web_url}/fleets/${ended ? 'history' : 'upcoming'}/${fleet_id}`)
    }

    // The killmail link goes on the clipboard and the SRP page opens: paste it into the request.
    file_srp(killmail_id) {
        if (!Number.isInteger(killmail_id) || !this.known_loss(killmail_id)) return
        this.clipboard.writeText(`https://zkillboard.com/kill/${killmail_id}/`)
        this.open_external(`${this.web_url}/ships/srp/killmails/`)
        this.mine_at = -Infinity
        this.flash('Killmail link copied')
    }

    async copy_fit(fleet_id, key) {
        const win = this.known_window(fleet_id)
        if (!win || !win.ships.some(s => s.key === key)) return
        try {
            const entry = (await this.composition(fleet_id)).find(e => e.key === key)
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

    async sign_up(fleet_id, key) {
        const win = this.known_window(fleet_id)
        if (!win || this.busy || !win.ships.some(s => s.key === key)) return
        const character_id = this.acting_character(win)
        if (!character_id) return this.flash('No character to sign up')
        await this.run('sign-up', () => this.api.set_my_ship(fleet_id, character_id, key), {
            done: 'Signed up',
            failed: err => err.status === 400 ? 'That ship is not in this fleet any more' : 'Could not sign up. Try again.',
        })
        this.mine_at = -Infinity
        return this.poll()
    }

    async refresh_motd() {
        const win = this.current_shown()
        if (!win || win.mode !== 'fc' || !win.fleet.live) return
        await this.run('motd', () => this.api.refresh_motd(win.fleet.id), { done: 'MOTD refreshed', failed: () => 'Could not refresh the MOTD' })
    }

    // Set destination: only systems the window is showing (the fleet, its form-up), for one of your
    // characters, one ESI write per click.
    async set_destination(system_id) {
        if (!Number.isInteger(system_id)) return
        const windows = [this.current, ...this.windows.values()].filter(Boolean)
        const win = windows.find(w => [w.fleet.fc_system_id, w.fleet.location_system_id].includes(system_id))
        if (!win) return
        const character_id = this.acting_character(win)
        if (!character_id) return this.flash('No character to route')
        const name = win.fleet.fc_system_id === system_id ? win.fleet.fc_system_name : win.fleet.location_system_name
        await this.run('destination', () => this.api.set_waypoint(character_id, system_id), {
            done: `Destination set: ${name || 'the fleet'}`,
            failed: err => err.detail || 'EVE did not take the destination',
        })
    }

    async preping(fleet_id) {
        const win = this.known_window(fleet_id)
        if (!win || win.mode !== 'fc' || win.fleet.live) return
        const sent = await this.run('preping', () => this.api.preping(fleet_id), { done: 'Pre-ping sent', failed: () => 'Could not send the pre-ping' })
        if (sent) {
            this.prepinged.add(fleet_id)
            this.publish()
        }
    }

    // Start tracking with the client in front as the in-game FC; the API pings Discord.
    async start(fleet_id) {
        const win = this.known_window(fleet_id)
        if (!win || win.mode !== 'fc' || win.fleet.live) return
        const fc_character_id = this.front.id && (win.me.character_ids || []).includes(this.front.id) ? this.front.id : null
        const started = await this.run('start', () => this.api.start_fleet(fleet_id, fc_character_id), {
            done: 'Fleet started',
            failed: err => err.detail || 'Could not start the fleet',
        })
        if (started) return this.poll()
    }

    toggle_reminder(fleet_id) {
        if (!this.store) return
        const row = this.list.find(f => f.id === fleet_id)
        if (!row) return
        const list = this.reminders()
        const on = list.some(r => r.id === fleet_id)
        const next = on ? list.filter(r => r.id !== fleet_id)
            : [...list, { id: fleet_id, at: row.start_time, title: row.doctrine || `${row.type_label} fleet`, where: row.location || '' }]
        this.store.set(REMINDERS_KEY, next.filter(r => new Date(r.at) - this.now() > -REMIND_LATE_MS))
        this.flash(on ? 'Reminder off' : 'Reminder set for 15 min before')
    }

    // Called every 30 s by main.js, whether or not the window is up.
    check_reminders() {
        const now = this.now()
        const list = this.reminders()
        for (const r of list) {
            const until = new Date(r.at) - now
            if (until <= REMIND_BEFORE_MS && until > -REMIND_LATE_MS && !this.reminded.has(r.id)) {
                this.reminded.add(r.id)
                const minutes = Math.max(0, Math.round(until / 60_000))
                this.notify(`${r.title} ${minutes ? `forms in ${minutes} min` : 'is forming'}`, r.where ? `Form up: ${r.where}` : 'Open the Fleets window for details')
            }
        }
        const kept = list.filter(r => new Date(r.at) - now > -REMIND_LATE_MS)
        if (kept.length !== list.length && this.store) this.store.set(REMINDERS_KEY, kept)
    }

    // One busy action at a time; the result shows in the status bar. Resolves true on success.
    async run(kind, action, { done, failed }) {
        if (this.busy) return false
        this.busy = kind
        this.publish()
        try {
            await action()
            this.flash(done)
            return true
        } catch (err) {
            if (err instanceof ApiError && err.status === 401) this.emit('unauthorized')
            else this.flash(failed(err))
            return false
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

module.exports = { FleetWindow, POLL_MS, MINE_POLL_MS, MAX_BACKOFF_MS, REMINDERS_KEY }
