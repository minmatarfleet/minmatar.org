// Notices a d-scan or Local list on the clipboard so the Intel window can open the report for it: the pilot
// copies in EVE (Ctrl+C) and the preview is there, no paste step. Main process only. While the Intel window
// is up (main.js: the intel poller's wanted rule) the clipboard text is read once a second and recognised
// here, on the PC. Anything else on the clipboard is never kept or sent: only a hash tells one copy from
// the next. A recognised copy is handed to on_copy, which starts the draft (intel.js paste).
const crypto = require('crypto')

const CHECK_MS = 1_000
const MAX_PASTE_CHARS = 200_000    // same cap as the API

// Same rules as the backend's detect_kind (backend/intel/services/paste.py), so what we open as a d-scan
// the preview reads as one. Local needs two names: one line of plain words is usually just chat.
const DSCAN_LINE = /^(\d+)\t([^\t]*)\t([^\t]+)\t([^\t]*)$/
const CHARACTER_NAME = /^[A-Za-z0-9][A-Za-z0-9 .'-]{1,35}[A-Za-z0-9.']$/

function detect_paste(text) {
    if (typeof text !== 'string' || !text.trim() || text.length > MAX_PASTE_CHARS) return null
    const lines = text.split('\n').map(line => line.replace(/^[\r ]+|[\r ]+$/g, '')).filter(line => line.trim())
    const dscan = lines.filter(line => DSCAN_LINE.test(line)).length
    if (dscan && dscan * 2 >= lines.length) return { kind: 'dscan', count: dscan }
    if (lines.length >= 2 && lines.every(line => CHARACTER_NAME.test(line.trim()))) {
        const names = new Set(lines.map(line => line.split(/\s+/).join(' ').toLowerCase()))
        return { kind: 'local', count: names.size }
    }
    return null
}

const fingerprint = text => crypto.createHash('sha256').update(text).digest('hex')

class ClipboardWatch {
    constructor({ read, on_copy, check_ms = CHECK_MS, timers = { setInterval, clearInterval } }) {
        this.read = read
        this.on_copy = on_copy
        this.check_ms = check_ms
        this.timers = timers
        this.timer = null
        this.seen = null       // fingerprint of the clipboard at the last check
        this.used = null       // fingerprint of the last text the window already has (Ctrl+V)
    }

    // Starting takes the clipboard as it is without opening it: whatever was copied before the window came
    // up (an hour-old scan) is left alone. Only a new copy opens a report.
    set_active(active) {
        if (active === !!this.timer) return
        if (!active) {
            this.timers.clearInterval(this.timer)
            this.timer = null
            this.seen = null
            return
        }
        this.seen = this.current().sig
        this.timer = this.timers.setInterval(() => this.check(), this.check_ms)
    }

    current() {
        let text = ''
        try { text = this.read() || '' } catch { /* clipboard busy (another app holds it): try next tick */ }
        return { text, sig: fingerprint(text) }
    }

    check() {
        const { text, sig } = this.current()
        if (sig === this.seen) return
        this.seen = sig
        if (sig === this.used) return
        const found = detect_paste(text)
        if (found) this.on_copy(text, found)
    }

    // The window got this text another way (Ctrl+V): don't open it a second time.
    mark_used(text) {
        if (typeof text === 'string') this.used = fingerprint(text)
    }
}

module.exports = { ClipboardWatch, detect_paste, CHECK_MS }
