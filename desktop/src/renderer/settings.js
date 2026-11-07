const $ = id => document.getElementById(id)
const { send, on_state, on_visibility } = window.minmatar
const { esc, portrait } = window.ui_helpers

window.eve_window.follow_visibility(on_visibility)

let windows_signature = null

function render_windows(windows) {
    const signature = JSON.stringify(windows)
    if (signature === windows_signature) return
    windows_signature = signature
    // A window closed to the tray this session is still on: Show brings it back (or use the tray).
    $('windows').innerHTML = windows.map(w => `
        <div class="setting">
            <label class="setting__label" for="window-${esc(w.id)}"><span class="setting__title">${esc(w.title)}${w.enabled && w.hidden ? ' <span class="setting__state">Hidden</span>' : ''}</span><span class="setting__text">${esc(w.description)}</span></label>
            ${w.enabled && w.hidden ? `<button class="eve-button setting__show" data-show-window="${esc(w.id)}">Show</button>` : ''}
            <input type="checkbox" class="switch" id="window-${esc(w.id)}" data-window="${esc(w.id)}" ${w.enabled ? 'checked' : ''}>
        </div>`).join('') +
        '<p class="eve-dim settings__hint">More windows are on the way.</p>'
}

function render_update(state) {
    const u = state.update || {}
    const button = $('update-button')
    let text = 'Up to date', label = null, command = null
    if (!state.updater_enabled) text = 'Updates are checked in installed builds'
    else if (u.status === 'checking') text = 'Checking for updates…'
    else if (u.status === 'error') { text = "Couldn't reach GitHub to check for updates"; label = 'Try again'; command = 'update:check' }
    else if (u.status === 'idle') { text = 'Not checked yet'; label = 'Check now'; command = 'update:check' }
    else if (u.status === 'ready') { text = `v${u.version} is ready`; label = 'Restart to update'; command = 'update:install' }
    else if (u.status === 'downloading') text = `Downloading v${u.version}… ${u.percent || 0}%`
    else if (u.status === 'available') { text = `v${u.version} is available`; label = 'Download'; command = 'update:download' }
    else { label = 'Check now'; command = 'update:check' }
    $('update-text').textContent = text
    button.hidden = !label
    button.textContent = label || ''
    button.dataset.command = command || ''
}

// Settings live on the account (src/main/settings.js); say where they stand when the API is slow or down.
const SYNC_TEXT = {
    synced: 'Settings are saved to your account.',
    saving: 'Saving settings to your account…',
    offline: "Can't reach Minmatar Fleet. Changes are kept and saved when it's back.",
    local: 'Loading your settings…',
}

on_state(state => {
    window.eve_window.apply(state)
    render_windows(state.windows || [])
    for (const input of document.querySelectorAll('[data-setting]')) input.checked = !!state.settings[input.dataset.setting]
    $('user').textContent = state.user ? state.user.name : ''
    $('api').textContent = state.api_url.replace(/^https?:\/\//, '')
    $('sync').textContent = SYNC_TEXT[state.settings_sync] || ''
    const id = state.user && state.user.character_id
    $('portrait').hidden = !id
    if (id && !$('portrait').src.includes(String(id))) $('portrait').src = portrait(id)
    $('version').textContent = `Minmatar Fleet v${state.version}`
    $('notice').textContent = state.notice
    render_update(state)
})

document.addEventListener('change', event => {
    const input = event.target
    if (input.dataset.setting) send('settings:set', { key: input.dataset.setting, value: input.checked })
    if (input.dataset.window) send('window:set-enabled', { id: input.dataset.window, enabled: input.checked })
})
document.addEventListener('click', event => {
    const show = event.target.closest('button[data-show-window]')
    if (show) return send('window:set-enabled', { id: show.dataset.showWindow, enabled: true })
    const button = event.target.closest('button[data-command]')
    if (button && button.dataset.command) send(button.dataset.command)
})
