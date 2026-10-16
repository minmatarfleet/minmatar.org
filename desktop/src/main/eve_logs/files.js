// Log file names and headers.
//
//   Chatlogs\<Channel Name>_<YYYYMMDD>_<HHMMSS>[_<characterId>].txt   UTF-16LE, one file per channel per session
//   Gamelogs\<YYYYMMDD>_<HHMMSS>[_<characterId>].txt                  UTF-8,    one file per character session
//
// Newer clients append the listener's character ID; older files don't have it. Timestamps are EVE time (UTC).
// Channel names can contain underscores and spaces, so the date/time/id suffix is matched from the end.

const CHAT_NAME = /^(.+)_(\d{8})_(\d{6})(?:_(\d+))?\.txt$/
const GAME_NAME = /^(\d{8})_(\d{6})(?:_(\d+))?\.txt$/

function stamp_to_date(day, time) {
    return new Date(Date.UTC(+day.slice(0, 4), +day.slice(4, 6) - 1, +day.slice(6, 8), +time.slice(0, 2), +time.slice(2, 4), +time.slice(4, 6)))
}

function parse_file_name(kind, name) {
    if (kind === 'chat') {
        const m = CHAT_NAME.exec(name)
        if (!m) return null
        return { kind, channel_name: m[1], started: stamp_to_date(m[2], m[3]), character_id: m[4] ? Number(m[4]) : null }
    }
    const m = GAME_NAME.exec(name)
    if (!m) return null
    return { kind, channel_name: null, started: stamp_to_date(m[1], m[2]), character_id: m[3] ? Number(m[3]) : null }
}

// Header block between two dashed lines:
//   Chat:  Channel ID / Channel Name / Listener / Session started
//   Game:  Gamelog / Listener / Session Started
const HEADER_FIELD = /^\s*([A-Za-z ]+?):\s*(.*?)\s*$/

function parse_header_line(line, header) {
    const m = HEADER_FIELD.exec(line)
    if (!m) return
    const key = m[1].trim().toLowerCase()
    if (key === 'channel id') header.channel_id = m[2]
    else if (key === 'channel name') header.channel_name = m[2]
    else if (key === 'listener') header.listener = m[2]
    else if (key === 'session started') header.session_started = m[2]
}

module.exports = { parse_file_name, parse_header_line, stamp_to_date }
