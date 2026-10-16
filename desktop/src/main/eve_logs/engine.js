// EVE log engine: tails the client's chat and game logs and turns them into events and state.
//
//   const engine = new EveLogEngine({ logs_dir }).start()
//   engine.on('ready', snapshot => ...)        // initial state rebuilt from today's logs
//   engine.on('system', e => ...)              // { character, from, to, time, source: 'local'|'jump' }
//   engine.on('chat', e => ...)                // every line, per listener
//   engine.on('message', e => ...)             // chat de-duplicated across your characters (intel!)
//   engine.on('game', e => ...)                // every game log line { kind, text, html }
//   engine.on('combat', e => ...)              // parsed combat line
//   engine.on('session', e => ...)             // a log file was picked up
//   engine.watch_channel(/intel/i, e => ...)   // hook a channel; returns an unsubscribe function
//   engine.character_by_name('Name') / engine.characters()
//
// It only reads files EVE writes for the player (see docs/desktop/ccp-third-party-guidelines.md).
const fs = require('fs')
const path = require('path')
const { EventEmitter } = require('events')
const { Tail } = require('./tail')
const { parse_file_name, parse_header_line } = require('./files')
const { parse_stamp, parse_chat_body, parse_game_body, local_system_change, jump, combat } = require('./parse')

const HOUR = 3_600_000

class LogSession {
    constructor(file, meta) {
        this.file = file
        this.kind = meta.kind
        this.started = meta.started
        this.header = { channel_name: meta.channel_name, channel_id: null, listener: null, session_started: null }
        this.character_id = meta.character_id
        this.tail = new Tail(file, { encoding: meta.kind === 'chat' ? 'utf16le' : 'utf8' })
        this.dashes = 0          // header sits between the first two dashed lines
        this.last = null         // last entry, for multi-line messages
    }

    get in_header() { return this.dashes < 2 }
}

class EveLogEngine extends EventEmitter {
    constructor({ logs_dir, poll_ms = 250, rescan_ms = 2000, max_age_hours = 36, idle_hours = 6, include_channel = null, now = () => Date.now() } = {}) {
        super()
        this.logs_dir = logs_dir
        this.poll_ms = poll_ms
        this.rescan_ms = rescan_ms
        this.max_age_ms = max_age_hours * HOUR
        this.idle_ms = idle_hours * HOUR
        this.include_channel = include_channel   // optional (channel_name) => bool, to skip channels you never need
        this.now = now
        this.sessions = new Map()                // file -> LogSession
        this.ignored = new Set()                 // files seen and skipped (too old / unparseable)
        this.chars = new Map()                   // key (id or name) -> character state
        this.recent_messages = new Map()         // de-dup key -> message event
        this.replaying = false
        this.started = false
    }

    // ------------------------------------------------------------------ lifecycle

    start() {
        if (this.started) return this
        this.started = true
        this.replaying = true          // catch up on today's files silently: state, no events
        this.rescan()
        this.poll()
        this.replaying = false
        this.emit('ready', this.snapshot())
        this.poll_timer = setInterval(() => this.safe(() => this.poll()), this.poll_ms)
        this.rescan_timer = setInterval(() => this.safe(() => this.rescan()), this.rescan_ms)
        return this
    }

    stop() {
        clearInterval(this.poll_timer)
        clearInterval(this.rescan_timer)
        for (const session of this.sessions.values()) session.tail.close()
        this.sessions.clear()
        this.started = false
    }

    safe(fn) {
        try { fn() } catch (err) { this.emit('error', err) }
    }

    // ------------------------------------------------------------------ queries

    characters() {
        return [...this.chars.values()].map(c => ({ ...c, channels: [...c.channels] }))
    }

    character(id) {
        const c = this.chars.get(String(id))
        return c ? { ...c, channels: [...c.channels] } : null
    }

    character_by_name(name) {
        const lower = String(name || '').toLowerCase()
        const c = [...this.chars.values()].find(x => x.name && x.name.toLowerCase() === lower)
        return c ? { ...c, channels: [...c.channels] } : null
    }

    snapshot() {
        return { characters: this.characters(), sessions: this.sessions.size }
    }

    // Hook one channel. matcher: exact channel name, RegExp, or (channel_name) => bool.
    // Receives the de-duplicated 'message' events for that channel.
    watch_channel(matcher, fn) {
        const test = typeof matcher === 'function' ? matcher
            : matcher instanceof RegExp ? name => matcher.test(name)
            : name => name === matcher
        const listener = event => { if (test(event.channel)) fn(event) }
        this.on('message', listener)
        return () => this.off('message', listener)
    }

    // ------------------------------------------------------------------ files

    rescan() {
        const cutoff = this.now() - this.max_age_ms
        for (const [kind, dir] of [['chat', 'Chatlogs'], ['game', 'Gamelogs']]) {
            const full = path.join(this.logs_dir, dir)
            let names
            try { names = fs.readdirSync(full) } catch (e) { continue }
            for (const name of names) {
                const file = path.join(full, name)
                if (this.sessions.has(file) || this.ignored.has(file)) continue
                const meta = parse_file_name(kind, name)
                // File names carry the session start, so old sessions are skipped without a stat per file.
                if (!meta || meta.started.getTime() < cutoff) { this.ignored.add(file); continue }
                if (kind === 'chat' && this.include_channel && !this.include_channel(meta.channel_name)) { this.ignored.add(file); continue }
                this.sessions.set(file, new LogSession(file, meta))
            }
        }
        // Drop sessions EVE stopped writing to (character logged off or a newer session replaced them).
        for (const [file, session] of this.sessions) {
            if (this.now() - session.tail.last_growth > this.idle_ms && session.started.getTime() < this.now() - this.idle_ms) {
                session.tail.close()
                this.sessions.delete(file)
                this.ignored.add(file)
            }
        }
    }

    poll() {
        // Read every file first, then dispatch all new lines in time order, so cross-file events
        // (a jump in the game log vs. the Local change) come out in the order they happened.
        const batch = []
        for (const [file, session] of this.sessions) {
            let lines
            try {
                lines = session.tail.read_lines()
            } catch (err) {
                session.tail.close()
                this.sessions.delete(file)       // deleted/moved; a rescan will pick up a replacement
                continue
            }
            if (lines.length) for (const entry of this.read_entries(session, lines)) batch.push({ session, entry })
        }
        batch.sort((a, b) => a.entry.time - b.entry.time)   // stable: same-second lines keep file order
        for (const { session, entry } of batch) {
            if (session.kind === 'chat') this.on_chat(session, entry)
            else this.on_game(session, entry)
        }
    }

    // ------------------------------------------------------------------ parsing

    read_entries(session, lines) {
        const entries = []
        for (const line of lines) {
            if (session.in_header) {
                if (/^\s*-{20,}\s*$/.test(line)) {
                    session.dashes++
                    if (!session.in_header) this.on_header(session)
                } else {
                    parse_header_line(line, session.header)
                }
                continue
            }
            const stamped = parse_stamp(line)
            if (stamped) {
                session.last = { time: stamped.time, rest: stamped.rest }
                entries.push(session.last)
            } else if (session.last && line.trim()) {
                // Multi-line message (MOTDs, fleet broadcasts with line breaks). EVE writes a message in one
                // go, so its continuation lines arrive in the same read as the first line.
                session.last.rest += '\n' + line
            }
        }
        return entries
    }

    on_header(session) {
        const c = this.char_for(session)
        if (c && session.kind === 'chat') c.channels.add(session.header.channel_name)
        if (!this.replaying) this.emit('session', { character: this.ref(c), kind: session.kind, channel: session.header.channel_name, file: session.file })
    }

    // null for logs with no character yet (EVE opens a game log at character select).
    char_for(session) {
        const listener = session.header.listener || null
        if (!listener && !session.character_id) return null
        const key = session.character_id ? String(session.character_id) : `name:${listener}`
        let c = this.chars.get(key)
        if (!c && session.character_id && listener) {
            // An older ID-less file may have created this character under its name first.
            const by_name = this.chars.get(`name:${listener}`)
            if (by_name) { this.chars.delete(`name:${listener}`); by_name.id = session.character_id; c = by_name; this.chars.set(key, c) }
        }
        if (!c) {
            c = { id: session.character_id, name: listener, system: null, system_since: null, last_jump: null, last_seen: null, channels: new Set() }
            this.chars.set(key, c)
        }
        if (listener && !c.name) c.name = listener
        return c
    }

    ref(c) {
        return c ? { id: c.id, name: c.name } : null
    }

    on_chat(session, entry) {
        const c = this.char_for(session)
        const { sender, text } = parse_chat_body(entry.rest)
        const channel = session.header.channel_name
        if (c) c.last_seen = max_time(c.last_seen, entry.time)

        const is_local = session.header.channel_id === 'local' || channel === 'Local'
        if (c && is_local) {
            const system = local_system_change(sender, text)
            if (system) this.set_system(c, system, entry.time, 'local')
        }
        if (this.replaying) return

        const event = { character: this.ref(c), channel, channel_id: session.header.channel_id, sender, text, time: entry.time }
        this.emit('chat', event)

        // The same line lands in every one of your characters' logs for a shared channel; emit it once.
        const key = `${channel}\u0000${entry.time.getTime()}\u0000${sender}\u0000${text}`
        const seen = this.recent_messages.get(key)
        if (seen) {
            if (c && !seen.listeners.some(l => l.id === c.id && l.name === c.name)) seen.listeners.push(this.ref(c))
            return
        }
        const message = { channel, channel_id: session.header.channel_id, sender, text, time: entry.time, listeners: c ? [this.ref(c)] : [] }
        this.recent_messages.set(key, message)
        if (this.recent_messages.size > 5000) this.recent_messages.delete(this.recent_messages.keys().next().value)
        this.emit('message', message)
    }

    on_game(session, entry) {
        const c = this.char_for(session)
        const body = parse_game_body(entry.rest)
        if (c) c.last_seen = max_time(c.last_seen, entry.time)

        if (c && body.kind === 'none') {
            const j = jump(body.text)
            if (j) {
                c.last_jump = { from: j.from, to: j.to, time: entry.time }
                this.set_system(c, j.to, entry.time, 'jump')
            }
        }
        if (this.replaying) return

        const event = { character: this.ref(c), kind: body.kind, text: body.text, html: body.html, time: entry.time }
        this.emit('game', event)
        if (body.kind === 'combat') this.emit('combat', { ...event, combat: combat(body.text) })
    }

    // Local and the game log both report a jump; whichever arrives first wins, the other is a no-op.
    set_system(c, system, time, source) {
        if (c.system === system) return
        if (c.system_since && time < c.system_since) return    // older line from another file: ignore
        const from = c.system
        c.system = system
        c.system_since = time
        if (!this.replaying) this.emit('system', { character: this.ref(c), from, to: system, time, source })
    }
}

function max_time(a, b) {
    return !a || b > a ? b : a
}

module.exports = { EveLogEngine }
