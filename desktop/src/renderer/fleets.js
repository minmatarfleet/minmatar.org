const $ = id => document.getElementById(id)
const { send, on_state, on_visibility } = window.minmatar
window.eve_window.follow_visibility(on_visibility)
const { eve_time, countdown, group_by_day } = window.fleet_format
const esc = value => String(value == null ? '' : value).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]))

let rendered = null   // signature of what the list currently shows
const SKELETON_ROWS = 4

function render_fleet(fleet) {
    const portrait = fleet.fc_character_id
        ? `<img class="fleet__portrait" src="https://images.evetech.net/characters/${encodeURIComponent(fleet.fc_character_id)}/portrait?size=64" alt="">`
        : '<span class="fleet__portrait"></span>'
    const status = fleet.live ? '<span class="fleet-live">Live</span>'
        : fleet.status === 'cancelled' ? '<span class="eve-danger">Cancelled</span>' : ''
    return `<div class="fleet${fleet.status === 'cancelled' ? ' fleet--cancelled' : ''}" role="button" tabindex="0" data-interactive data-fleet="${fleet.id}" title="Open fleet on my.minmatar.org">
        ${portrait}
        <div class="fleet__headline">
            <span class="fleet-type fleet-type--${esc(fleet.type)}">${esc(fleet.type_label)}</span>
            <span class="fleet__doctrine">${esc(fleet.doctrine || fleet.audience || 'Fleet')}</span>
            ${status}
        </div>
        <span class="fleet__when">${eve_time(fleet.start_time)}</span>
        <div class="fleet__meta"><span class="fleet__fc">${esc(fleet.fc_name)}</span>${fleet.location ? ` · ${esc(fleet.location)}` : ''}${fleet.audience && fleet.doctrine ? ` · ${esc(fleet.audience)}` : ''}</div>
        <span class="fleet__countdown" data-start="${esc(fleet.start_time)}">${countdown(fleet.start_time)}</span>
        ${fleet.description ? `<div class="fleet__description">${esc(fleet.description)}</div>` : ''}
    </div>`
}

function render_skeleton() {
    return '<div class="fleet-group"><span class="skeleton skeleton--short"></span></div>' +
        Array.from({ length: SKELETON_ROWS }, () =>
            `<div class="fleet fleet--skeleton" aria-hidden="true">
                <span class="fleet__portrait skeleton"></span>
                <span class="skeleton"></span><span class="skeleton skeleton--short"></span>
                <span class="skeleton skeleton--wide"></span>
            </div>`).join('')
}

function render_list(state) {
    if (!state.fleets.length) {
        // First load (nothing to show yet): placeholder rows instead of a blank window.
        if (state.loading || !state.updated_at && !state.error) return render_skeleton()
        return '<div class="eve-empty">No fleets scheduled.</div>'
    }
    return group_by_day(state.fleets).map(group =>
        `<div class="fleet-group${group.label === 'Live now' ? ' fleet-group--live' : ''}"><span>${esc(group.label)}</span><span class="eve-dim">${group.fleets.length}</span></div>` +
        group.fleets.map(render_fleet).join('')
    ).join('')
}

on_state(state => {
    window.eve_window.apply(state)
    $('overlay').setAttribute('aria-pressed', String(state.overlay))
    $('refresh').classList.toggle('is-loading', state.loading)
    $('title').textContent = `Upcoming Fleets (${state.fleets.length})`
    const who = state.location ? `${state.location.character} · ${state.location.system}` : (state.user ? state.user.name : '')
    $('status').textContent = `${who}${state.updated_at ? ` · updated ${eve_time(state.updated_at)} EVE` : ''}`

    $('version').textContent = `v${state.version}`
    const update = state.update || {}
    $('update').hidden = !['ready', 'available'].includes(update.status)
    $('update').textContent = update.status === 'ready' ? `Restart to update (v${update.version})` : `v${update.version} available`
    $('update').dataset.action = update.status === 'ready' ? 'update:install' : 'update:download'

    // State is pushed on every focus change; only rebuild the list when its content changed,
    // so rows (and portraits) don't flicker while you switch windows.
    const skeleton = !state.fleets.length && (state.loading || !state.updated_at && !state.error)
    const signature = JSON.stringify([state.fleets, state.error, skeleton])
    if (signature === rendered) return
    const first_data = rendered !== null && rendered.endsWith('true]') && !skeleton
    rendered = signature
    $('list').innerHTML = (state.error ? `<p class="eve-error">${esc(state.error)}</p>` : '') + render_list(state)
    if (first_data) $('list').classList.add('is-arriving')
})
$('list').addEventListener('animationend', () => $('list').classList.remove('is-arriving'))

// Countdowns tick locally; the list itself refreshes from the API every minute.
setInterval(() => {
    document.querySelectorAll('.fleet__countdown').forEach(el => { el.textContent = countdown(el.dataset.start) })
}, 1000)

window.eve_window.wire_overlay(send)
$('sign-out').addEventListener('click', () => send('auth:sign-out'))
$('update').addEventListener('click', () => send($('update').dataset.action))

$('list').addEventListener('click', event => {
    const row = event.target.closest('[data-fleet]')
    if (row) send('fleets:open', Number(row.dataset.fleet))
})
$('list').addEventListener('keydown', event => {
    const row = event.target.closest('[data-fleet]')
    if (row && (event.key === 'Enter' || event.key === ' ')) {
        event.preventDefault()
        send('fleets:open', Number(row.dataset.fleet))
    }
})
