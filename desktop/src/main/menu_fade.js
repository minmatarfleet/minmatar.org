// Fade on right-click: EVE draws its context menus inside the client, and our windows sit just above the
// client, so a menu that opens under one of them is hidden. When the pilot right-clicks in a client, the
// windows near the click are hidden (page and native glass both), so the menu can be seen and clicked. They
// come back once the click that picks or dismisses the menu is released.
//
// Button events come from the native helper (eve_clients.js 'button'); positions are physical pixels.
const { EventEmitter } = require('events')

// Area a context menu (plus a submenu or two) can cover around the click, at UI scale 1. Menus open down and
// right of the cursor and flip up or left near the screen edge; submenus open to the side.
const MENU_REACH = { left: 300, right: 600, up: 550, down: 550 }
// Esc closes a menu without a click, and we don't read the keyboard, so give up waiting after this.
const MENU_TIMEOUT_MS = 20_000

function menu_zone(point, ui_scale = 1) {
    const s = ui_scale > 0 ? ui_scale : 1
    return {
        x: Math.round(point.x - MENU_REACH.left * s),
        y: Math.round(point.y - MENU_REACH.up * s),
        width: Math.round((MENU_REACH.left + MENU_REACH.right) * s),
        height: Math.round((MENU_REACH.up + MENU_REACH.down) * s),
    }
}

function intersects(a, b) {
    return a.x < b.x + b.width && b.x < a.x + a.width && a.y < b.y + b.height && b.y < a.y + a.height
}

// Emits 'fade' (zone) when a menu opens and 'restore' when it's gone.
class MenuFade extends EventEmitter {
    constructor({ timeout_ms = MENU_TIMEOUT_MS } = {}) {
        super()
        this.timeout_ms = timeout_ms
        this.open = false
        this.closing = false
    }

    button(event, ui_scale = 1) {
        if (event.b === 'r' && event.down && event.eve) {
            // A right-click in a client opens a menu (or replaces the open one).
            this.open = true
            this.closing = false
            this.arm_timeout()
            this.emit('fade', menu_zone(event, ui_scale))
        } else if (this.open && event.down) {
            // The click that picks an entry or dismisses the menu. Stay faded until it's released,
            // so the press and release both land in EVE.
            this.closing = true
        } else if (this.open && this.closing && !event.down) {
            this.restore()
        }
    }

    restore() {
        clearTimeout(this.timer)
        if (!this.open) return
        this.open = false
        this.closing = false
        this.emit('restore')
    }

    arm_timeout() {
        clearTimeout(this.timer)
        this.timer = setTimeout(() => this.restore(), this.timeout_ms)
    }
}

module.exports = { MenuFade, menu_zone, intersects, MENU_REACH, MENU_TIMEOUT_MS }
