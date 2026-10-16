// Where Sneak sits: peeking over the top of EVE's notification badge.
//
// EVE anchors the badge to the bottom-right of the client. `notification_badge_offset` (core_char_<id>.dat)
// is its distance from that corner in UI units, default (16, 16); the badge is 32 UI units square.
// UI units become pixels through EVE's UI scale (core_public__.yaml). Calibrated against a 3440x1440
// client at scale 1.0: the badge spans x 3392-3424, y 1392-1424.
const BADGE_SIZE = 32
const DEFAULT_OFFSET = [16, 16]
const MASCOT = { width: 40, height: 36, overlap: 1 }   // UI units; head art is 239x212

// Physical-pixel rects; `client` is { x, y, w, h } of the EVE client area.
function badge_rect(client, { offset = DEFAULT_OFFSET, scale = 1 } = {}) {
    const [ox, oy] = offset || DEFAULT_OFFSET
    const size = BADGE_SIZE * scale
    return {
        x: Math.round(client.x + client.w - ox * scale - size),
        y: Math.round(client.y + client.h - oy * scale - size),
        width: Math.round(size),
        height: Math.round(size),
    }
}

function mascot_rect(client, options = {}) {
    const scale = options.scale || 1
    const badge = badge_rect(client, options)
    const width = Math.round(MASCOT.width * scale)
    const height = Math.round(MASCOT.height * scale)
    return {
        x: Math.round(badge.x + badge.width / 2 - width / 2),
        y: Math.round(badge.y - height + MASCOT.overlap * scale),   // ducks a hair behind the badge's top edge
        width,
        height,
    }
}

module.exports = { badge_rect, mascot_rect, BADGE_SIZE, DEFAULT_OFFSET }
