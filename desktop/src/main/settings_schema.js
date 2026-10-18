// The pilot's desktop settings, saved on the account (settings.js; GET/PATCH /api/users/me/desktop-settings
// as a merge of the keys that changed). Every copy of the app the pilot runs reads and writes the same keys
// at the same time: two PCs, an installer and a portable exe, an old version and a new one. So each key's
// shape is a contract between versions:
//
//   key                    value                                              default
//   locked                 boolean: windows pinned (no drag/resize)            true
//   show_sneak             boolean: Sneak on EVE's notification badge          true
//   fade_on_right_click    boolean: hide windows near a right-click menu       true
//   window.<id>            { enabled?: boolean, bounds?: {x, y, width, height}  enabled: windows.js default_enabled
//                            (DIPs), range?: integer jumps | null (intel) }
//   fleet_reminders        [{ id: fleet id, at: ISO start, title, where }]     []
//
// Rules (also in .claude/rules/desktop-release.md):
//   - Never change the shape or meaning of an existing key or field. A new shape gets a new key name, and
//     the new version reads the old key as a fallback. Anything else is a major version.
//   - Reads go through this file: an invalid or unknown value reads as the default, and a read never
//     writes, so a value another version wrote is never "fixed" here and overwritten on its account.
//   - Writes to an object key spread the stored value (stored_window), so fields a newer version added
//     survive an older version's save. Keys this version doesn't know are left alone.
const TOGGLES = { locked: true, show_sneak: true, fade_on_right_click: true }
const WINDOW_PREFIX = 'window.'
const REMINDERS_KEY = 'fleet_reminders'

const is_object = value => !!value && typeof value === 'object' && !Array.isArray(value)

// One of the TOGGLES, or its default when the stored value isn't a boolean.
function read_toggle(key, value) {
    return typeof value === 'boolean' ? value : TOGGLES[key]
}

const window_key = id => `${WINDOW_PREFIX}${id}`

// The stored window.<id> object as it is, for merging a change into (never null).
function stored_window(value) {
    return is_object(value) ? value : {}
}

// Saved bounds the window can be placed at, else null (the window opens at its default spot).
function read_bounds(value) {
    if (!is_object(value)) return null
    const { x, y, width, height } = value
    return [x, y, width, height].every(Number.isFinite) ? { x, y, width, height } : null
}

// Intel's range: a whole number of jumps (never below 0), null for any distance, undefined for "not set".
function read_range(value) {
    if (value === null) return null
    return Number.isInteger(value) ? Math.max(0, value) : undefined
}

// window.<id> as this version uses it. def: the window's entry in windows.js.
function read_window(value, def) {
    const saved = stored_window(value)
    return {
        enabled: typeof saved.enabled === 'boolean' ? saved.enabled : !!(def && def.default_enabled),
        bounds: read_bounds(saved.bounds),
        range: read_range(saved.range),
    }
}

// The "Remind me" list; entries without a fleet id are skipped.
function read_reminders(value) {
    return Array.isArray(value) ? value.filter(r => is_object(r) && Number.isInteger(r.id)) : []
}

module.exports = {
    TOGGLES, WINDOW_PREFIX, REMINDERS_KEY,
    read_toggle, window_key, stored_window, read_bounds, read_range, read_window, read_reminders,
}
