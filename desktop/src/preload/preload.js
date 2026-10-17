// The only bridge between the windows and the main process. No token, no Node APIs:
// windows get a state snapshot and can send a fixed set of commands.
const { contextBridge, ipcRenderer } = require('electron')

// The same list as src/main/ipc_commands.js, which a sandboxed preload can't require. test/ipc.test.js
// fails when the two differ: add a command there and here.
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

contextBridge.exposeInMainWorld('minmatar', {
    on_state: fn => ipcRenderer.on('state', (event, state) => fn(state)),
    on_visibility: fn => ipcRenderer.on('visibility', (event, visible) => fn(visible)),
    on_fleet: fn => ipcRenderer.on('fleet', (event, snapshot) => fn(snapshot)),
    send: (command, value) => {
        if (COMMANDS.includes(command)) ipcRenderer.send(command, value)
    },
})
