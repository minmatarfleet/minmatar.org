// Line parsers. Pure functions, no I/O.

// "[ 2026.10.15 23:01:22 ] rest"
const STAMPED = /^\s*\[ (\d{4})\.(\d\d)\.(\d\d) (\d\d):(\d\d):(\d\d) \] (.*)$/

function parse_stamp(line) {
    const m = STAMPED.exec(line)
    if (!m) return null
    return { time: new Date(Date.UTC(+m[1], +m[2] - 1, +m[3], +m[4], +m[5], +m[6])), rest: m[7] }
}

// Chat: "<sender> > <message>". Sender names can't contain " > ", messages can.
function parse_chat_body(rest) {
    const i = rest.indexOf(' > ')
    if (i < 0) return { sender: '', text: rest }
    return { sender: rest.slice(0, i), text: rest.slice(i + 3) }
}

// Game: "(<kind>) <html message>"
function parse_game_body(rest) {
    const m = /^\((\w+)\) ?(.*)$/.exec(rest)
    if (!m) return { kind: 'unknown', html: rest, text: strip_markup(rest) }
    return { kind: m[1].toLowerCase(), html: m[2], text: strip_markup(m[2]) }
}

const ENTITIES = { '&lt;': '<', '&gt;': '>', '&amp;': '&', '&quot;': '"', '&#39;': "'", '&apos;': "'", '&nbsp;': ' ' }
function strip_markup(html) {
    return html
        .replace(/<br\s*\/?>/gi, '\n')
        .replace(/<[^>]*>/g, '')
        .replace(/&(lt|gt|amp|quot|#39|apos|nbsp);/g, e => ENTITIES[e])
        .replace(/[ \t]+/g, ' ')
        .trim()
}

// "EVE System > Channel changed to Local : Amamake". Only the Local channel means a solar system;
// the same message is posted for Corp/Alliance/Militia with the corp/alliance name.
// English client strings; other client languages can be added here.
const LOCAL_CHANGE = [/^Channel changed to Local : (.+?)\*?$/]

function local_system_change(sender, text) {
    if (sender !== 'EVE System') return null
    for (const pattern of LOCAL_CHANGE) {
        const m = pattern.exec(text.trim())
        if (m) return m[1].trim()
    }
    return null
}

// "(None) Jumping from Amamake to Siseide"
function jump(text) {
    const m = /^Jumping from (.+) to (.+)$/.exec(text)
    return m ? { from: m[1].trim(), to: m[2].trim() } : null
}

// Combat lines, after markup is stripped. The pilot/ship part depends on the player's combat-log
// format setting, so it is kept as one raw `other` string rather than split into ship/corp/pilot.
const QUALITIES = ['Hits', 'Penetrates', 'Smashes', 'Grazes', 'Glances Off', 'Wrecks', 'Scratches']

function combat(text) {
    let m = /^(\d+) (to|from) (.+)$/.exec(text)
    if (m) {
        const parts = m[3].split(' - ')
        const quality = QUALITIES.includes(parts[parts.length - 1]) ? parts.pop() : null
        const weapon = parts.length >= 2 ? parts.pop() : null
        return { type: 'damage', direction: m[2] === 'to' ? 'out' : 'in', amount: Number(m[1]), other: parts.join(' - '), weapon, quality }
    }
    m = /^(\d+) remote (\w+) (?:\w+ )?(to|by) (.+?)(?: - (.+))?$/.exec(text)
    if (m) return { type: 'remote_repair', direction: m[3] === 'to' ? 'out' : 'in', amount: Number(m[1]), layer: m[2], other: m[4], weapon: m[5] || null }
    m = /^(Warp disruption|Warp scramble) attempt from (.+?)(?: -)? to (.+?)(?: -.*)?$/.exec(text)
    if (m) return { type: m[1] === 'Warp scramble' ? 'warp_scramble' : 'warp_disruption', source: m[2].trim(), target: m[3].trim() }
    m = /^Your (.+?) misses (.+?) completely(?: - (.+))?$/.exec(text)
    if (m) return { type: 'miss', direction: 'out', other: m[2], weapon: m[3] || m[1] }
    m = /^(.+?) misses you completely(?: - (.+))?$/.exec(text)
    if (m) return { type: 'miss', direction: 'in', other: m[1], weapon: m[2] || null }
    m = /^(\d+) GJ energy (neutralized|drained) (?:from|to)? ?(.+?)(?: - (.+))?$/.exec(text)
    if (m) return { type: m[2] === 'neutralized' ? 'neut' : 'nos', amount: Number(m[1]), other: m[3], weapon: m[4] || null }
    return { type: 'other' }
}

module.exports = { parse_stamp, parse_chat_body, parse_game_body, strip_markup, local_system_change, jump, combat }
