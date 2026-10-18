// Every command a window may send to the main process, and the checks on the values they carry.
//
// The windows are untrusted: a value from a renderer is only used after it passes one of these checks,
// and fleet_window.js / intel.js then act only on fleets, ships, killmails and reports they are showing.
// preload.js keeps its own copy of COMMANDS (a sandboxed preload can't require local files);
// test/ipc.test.js fails when that copy, this list and main.js's handlers disagree.
const COMMANDS = [
    'login:start', 'login:cancel', 'auth:sign-out',
    'app:refresh', 'campaigns:open', 'lock:toggle',
    'window:minimize', 'window:close', 'mouse:interactive',
    'drag:start', 'drag:move', 'drag:end',
    'update:install', 'update:download', 'update:check',
    'settings:open', 'settings:set', 'window:set-enabled',
    'fleet:open', 'fleet:close', 'fleet:open-site', 'fleet:refresh-motd', 'fleet:copy-fit', 'fleet:sign-up',
    'fleet:srp', 'fleet:dismiss-loss', 'fleet:done', 'fleet:destination', 'fleet:preping', 'fleet:start', 'fleet:remind',
    'intel:paste', 'intel:paste-text', 'intel:kind', 'intel:edit', 'intel:share', 'intel:discard',
    'intel:open-report', 'intel:close-report', 'intel:copy-link', 'intel:open-site', 'intel:range',
]

// A positive integer id (fleet, killmail, system), else null.
const id_of = value => (Number.isSafeInteger(value) && value > 0 ? value : null)

// A doctrine ship key from the fleet window payload ("f:12" fitting, "m:3" member ship), else null.
const fleet_key = value => (typeof value === 'string' && /^[fm]:\d+$/.test(value) ? value : null)

// { fleet_id, key } for copy-fit and sign-up, else null.
const fleet_ship = value => (value && id_of(value.fleet_id) && fleet_key(value.key) ? { fleet_id: value.fleet_id, key: value.key } : null)

// The Intel window's range: a whole number of jumps, or null for any distance. undefined when invalid.
const intel_range = value => (value === null || Number.isInteger(value) ? value : undefined)

// { id, enabled } from the Settings window's window list, else null.
const window_toggle = value => (value && typeof value.id === 'string' && typeof value.enabled === 'boolean' ? { id: value.id, enabled: value.enabled } : null)

module.exports = { COMMANDS, id_of, fleet_key, fleet_ship, intel_range, window_toggle }
