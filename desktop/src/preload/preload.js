// The only bridge between the windows and the main process. No token, no Node APIs:
// windows get a state snapshot and can send a fixed set of commands.
const { contextBridge, ipcRenderer } = require('electron')

const COMMANDS = [
    'login:start', 'login:cancel', 'auth:sign-out',
    'fleets:refresh', 'fleets:open', 'overlay:toggle',
    'window:minimize', 'window:close', 'mouse:interactive',
    'resize:start', 'resize:move', 'resize:end',
    'update:install', 'update:download', 'update:check',
    'settings:open', 'settings:set', 'window:set-enabled',
    'intel:refresh', 'intel:paste', 'intel:paste-text', 'intel:kind', 'intel:edit', 'intel:share', 'intel:discard',
    'intel:open-report', 'intel:close-report', 'intel:copy-link', 'intel:open-site', 'intel:range',
]

contextBridge.exposeInMainWorld('minmatar', {
    on_state: fn => ipcRenderer.on('state', (event, state) => fn(state)),
    on_visibility: fn => ipcRenderer.on('visibility', (event, visible) => fn(visible)),
    send: (command, value) => {
        if (COMMANDS.includes(command)) ipcRenderer.send(command, value)
    },
})
