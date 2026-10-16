// Reads a few of the EVE client's own UI settings so our windows match it: window transparency,
// where the notification badge sits, and the UI scale.
//
// EVE saves per-character UI settings in
//   %LOCALAPPDATA%\CCP\EVE\<install>_tq_tranquility\settings_<profile>\core_char_<characterId>.dat
// in CCP's binary marshal format. Each setting is stored value-first:
//   2c (tuple of two)  2f LL <LL-byte FILETIME saved-at>  <value>  13 <len> <key>
// Photon's Settings > Windows slider is saved as `windowTransparency` (dark windows, 0..1,
// default 1.0) and `windowTransparencyLightMode` (windows set to Light Background).
//
// Display settings (UI scale, window mode) live next to them in plain YAML: core_public__.yaml.
//
// We only read these files. Nothing is ever written to EVE's settings.
const fs = require('fs')
const path = require('path')
const { EventEmitter } = require('events')

const DEFAULT_TRANSPARENCY = 1.0

// Value of a numeric setting, or null if absent. Accepts the encodings marshal uses for floats/ints.
function read_number_setting(buffer, key) {
    const token = Buffer.concat([Buffer.from([0x13, key.length]), Buffer.from(key, 'latin1')])
    let at = buffer.indexOf(token)
    while (at !== -1) {
        const value = value_before(buffer, at)
        if (value !== null) return value
        at = buffer.indexOf(token, at + 1)
    }
    return null
}

function value_before(buffer, at) {
    const candidates = []
    if (at >= 9 && buffer[at - 9] === 0x0a) candidates.push([at - 9, buffer.readDoubleLE(at - 8)])   // float64
    if (buffer[at - 1] === 0x0b) candidates.push([at - 1, 0])                                        // float zero
    if (buffer[at - 1] === 0x08) candidates.push([at - 1, 0])                                        // int zero
    if (buffer[at - 1] === 0x09) candidates.push([at - 1, 1])                                        // int one
    if (at >= 2 && buffer[at - 2] === 0x06) candidates.push([at - 2, buffer.readInt8(at - 1)])       // int8
    for (const [start, value] of candidates) {
        // Must be the second half of (saved-at FILETIME, value), so a stray byte can't match.
        for (let len = 1; len <= 8; len++) {
            const head = start - len - 3
            if (head >= 0 && buffer[head] === 0x2c && buffer[head + 1] === 0x2f && buffer[head + 2] === len) return value
        }
    }
    return null
}

// Marshalled ints that can end at `end`: [start, value] candidates.
function ints_ending_at(buffer, end) {
    const out = []
    const op1 = buffer[end - 1]
    if (op1 === 0x07) out.push([end - 1, -1])
    if (op1 === 0x08) out.push([end - 1, 0])
    if (op1 === 0x09) out.push([end - 1, 1])
    if (end >= 2 && buffer[end - 2] === 0x06) out.push([end - 2, buffer.readInt8(end - 1)])
    if (end >= 3 && buffer[end - 3] === 0x05) out.push([end - 3, buffer.readInt16LE(end - 2)])
    if (end >= 5 && buffer[end - 5] === 0x04) out.push([end - 5, buffer.readInt32LE(end - 4)])
    return out
}

// A setting whose value is a pair of ints, e.g. notification_badge_offset = (16, 16):
//   2c 2f LL <FILETIME>  2c <int> <int>  13 <len> <key>
function read_int_pair_setting(buffer, key) {
    const token = Buffer.concat([Buffer.from([0x13, key.length]), Buffer.from(key, 'latin1')])
    for (let at = buffer.indexOf(token); at !== -1; at = buffer.indexOf(token, at + 1)) {
        for (const [second_start, second] of ints_ending_at(buffer, at)) {
            for (const [first_start, first] of ints_ending_at(buffer, second_start)) {
                const tuple = first_start - 1
                if (buffer[tuple] !== 0x2c) continue
                for (let len = 1; len <= 8; len++) {
                    const head = tuple - len - 3
                    if (head >= 0 && buffer[head] === 0x2c && buffer[head + 1] === 0x2f && buffer[head + 2] === len) return [first, second]
                }
            }
        }
    }
    return null
}

// core_public__.yaml lines look like `  UIScaleWindowed: [134366345551403519, 1.0]` (saved-at, value).
function read_public_settings(profile_dir) {
    const out = {}
    let text = ''
    try { text = fs.readFileSync(path.join(profile_dir, 'core_public__.yaml'), 'utf8') } catch (e) { return out }
    for (const line of text.split(/\r?\n/)) {
        const m = /^\s*(\w+):\s*\[\s*-?\d+\s*,\s*(.+?)\s*\]\s*$/.exec(line)
        if (!m) continue
        const raw = m[2]
        out[m[1]] = raw === 'true' ? true : raw === 'false' ? false : raw === 'null' ? null : Number.isFinite(Number(raw)) ? Number(raw) : raw
    }
    return out
}

// EVE's UI scale for the current display mode (WindowMode 0 = fullscreen; anything else is windowed).
function ui_scale_from(public_settings) {
    const fullscreen = public_settings.WindowMode === 0
    const value = fullscreen ? public_settings.UIScaleFullscreen : public_settings.UIScaleWindowed
    return typeof value === 'number' && value > 0.5 && value < 4 ? value : 1
}

// All core_char_<id>.dat files across Tranquility installs and settings profiles.
function find_character_files(local_app_data) {
    const root = path.join(local_app_data, 'CCP', 'EVE')
    const files = []
    let installs = []
    try { installs = fs.readdirSync(root).filter(name => name.endsWith('_tq_tranquility')) } catch (e) { return files }
    for (const install of installs) {
        let profiles = []
        try { profiles = fs.readdirSync(path.join(root, install)).filter(name => /^settings_[^.]+$/.test(name) && !/_backup\d*$/.test(name)) } catch (e) { continue }
        for (const profile of profiles) {
            const dir = path.join(root, install, profile)
            let names = []
            try { names = fs.readdirSync(dir) } catch (e) { continue }
            for (const name of names) {
                const m = /^core_char_(\d+)\.dat$/.exec(name)
                if (!m) continue
                try {
                    const file = path.join(dir, name)
                    files.push({ file, character_id: Number(m[1]), mtime: fs.statSync(file).mtimeMs })
                } catch (e) {}
            }
        }
    }
    return files
}

// Tracks the transparency for one character (or, with none chosen, the most recently saved one,
// which is whoever played last) and emits 'change' when EVE saves a new value.
class EveWindowSettings extends EventEmitter {
    constructor({ local_app_data, poll_ms = 3000 }) {
        super()
        this.local_app_data = local_app_data
        this.poll_ms = poll_ms
        this.character_id = null
        this.current = { transparency: DEFAULT_TRANSPARENCY, character_id: null, found: false, badge_offset: null, ui_scale: 1 }
        this.seen = ''
    }

    start() {
        this.poll()
        this.timer = setInterval(() => this.poll(), this.poll_ms)
        return this
    }

    stop() { clearInterval(this.timer) }

    set_character(character_id) {
        if (character_id === this.character_id) return
        this.character_id = character_id
        this.poll()
    }

    poll() {
        const files = find_character_files(this.local_app_data)
        const mine = this.character_id ? files.filter(f => f.character_id === this.character_id) : files
        const latest = mine.sort((a, b) => b.mtime - a.mtime)[0]
        const key = latest ? `${latest.file}|${latest.mtime}` : 'none'
        if (key === this.seen) return
        this.seen = key

        let transparency = null
        let badge_offset = null
        let ui_scale = 1
        if (latest) {
            try {
                const buffer = fs.readFileSync(latest.file)
                transparency = read_number_setting(buffer, 'windowTransparency')
                badge_offset = read_int_pair_setting(buffer, 'notification_badge_offset')
            } catch (e) {}
            ui_scale = ui_scale_from(read_public_settings(path.dirname(latest.file)))
        }
        const next = {
            transparency: transparency === null ? DEFAULT_TRANSPARENCY : Math.min(1, Math.max(0, transparency)),
            character_id: latest ? latest.character_id : null,
            found: transparency !== null,
            badge_offset,
            ui_scale,
        }
        if (JSON.stringify(next) !== JSON.stringify(this.current)) {
            this.current = next
            this.emit('change', next)
        }
    }
}

// ESI etiquette (docs/desktop/ccp-third-party-guidelines.md rule 12): identify the app and pin the API version.
const ESI_HEADERS = {
    'User-Agent': `MinmatarFleetDesktop/${require('../../package.json').version} (+https://github.com/minmatarfleet/minmatar.org)`,
    'X-Compatibility-Date': '2025-08-26',
}

// "EVE - <name>" -> character ID via ESI's public name lookup, cached for the session.
const id_cache = new Map()
async function character_id_for_name(name, fetch_impl = globalThis.fetch) {
    if (!name) return null
    if (id_cache.has(name)) return id_cache.get(name)
    try {
        const response = await fetch_impl('https://esi.evetech.net/universe/ids', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', Accept: 'application/json', ...ESI_HEADERS },
            body: JSON.stringify([name]),
        })
        if (!response.ok) return null
        const body = await response.json()
        const match = (body.characters || []).find(c => c.name.toLowerCase() === name.toLowerCase())
        const id = match ? match.id : null
        id_cache.set(name, id)
        return id
    } catch (e) {
        return null
    }
}

module.exports = { read_number_setting, read_int_pair_setting, read_public_settings, ui_scale_from, find_character_files, EveWindowSettings, character_id_for_name, DEFAULT_TRANSPARENCY, ESI_HEADERS }
