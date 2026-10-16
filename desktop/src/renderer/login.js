const $ = id => document.getElementById(id)
const { send, on_state, on_visibility } = window.minmatar
window.eve_window.follow_visibility(on_visibility)

document.querySelectorAll('[data-command]').forEach(button => {
    button.addEventListener('click', () => send(button.dataset.command))
})
$('sign-in').addEventListener('click', () => send('login:start'))
$('cancel').addEventListener('click', () => send('login:cancel'))

on_state(state => {
    window.eve_window.apply(state)
    $('sign-in').disabled = state.login.pending
    $('pending').hidden = !state.login.pending
    $('error').hidden = !state.login.error
    $('error').textContent = state.login.error || ''
    $('api').textContent = state.api_url.replace(/^https?:\/\//, '')
    $('version').textContent = `v${state.version}`
})
