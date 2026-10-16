const $ = id => document.getElementById(id)
const { send, on_state, on_visibility, on_fleet } = window.minmatar
window.eve_window.follow_visibility(on_visibility)
const { eve_time, countdown, group_by_day } = window.fleet_format
const { render: render_fleet_view, elapsed, until } = window.fleet_view
const esc = value => String(value == null ? '' : value).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]))

let rendered = null   // signature of what the list currently shows
let list_title = 'Upcoming Fleets'
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
    list_title = `Upcoming Fleets (${state.fleets.length})`
    if (!fleet_shown()) $('title').textContent = list_title
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

// ---------------------------------------------------------------- fleet view (src/renderer/fleet_view.js)

let fleet = null                                      // latest snapshot from the main process
const fleet_ui = { tab: 'summary', compact: false }   // local only: which FC tab, window at min size
const COMPACT_HEIGHT = 360

function fleet_shown() {
    return !!fleet && fleet.view !== 'list'
}

// Rewrite a part only when its HTML changed: a poll with nothing new leaves the DOM (and its images) alone.
function patch(el, html) {
    if (el.__html === html) return false
    el.__html = html
    el.innerHTML = html
    el.querySelectorAll('[data-pct]').forEach(bar => { bar.style.width = `${bar.dataset.pct}%` })
    return true
}

let last_view = null
function render_fleet() {
    const shown = fleet_shown()
    $('list').hidden = shown
    $('list-footer').hidden = shown
    $('fleet').hidden = !shown
    $('back').hidden = !shown
    if (!shown) {
        $('title').textContent = list_title
        last_view = null
        return
    }
    const parts = render_fleet_view(fleet, fleet_ui)
    $('title').textContent = parts.title
    patch($('fleet-top'), parts.top)
    $('fleet-top').hidden = !parts.top
    if (patch($('fleet-main'), parts.main) && fleet.view !== last_view) $('fleet-main').scrollTop = 0
    patch($('fleet-foot'), parts.foot)
    last_view = fleet.view
}

on_fleet(snapshot => {
    fleet = snapshot
    render_fleet()
})

$('fleet').addEventListener('click', event => {
    const tab = event.target.closest('[data-tab]')
    if (tab) {
        fleet_ui.tab = tab.dataset.tab
        return render_fleet()
    }
    const action = event.target.closest('[data-fleet-command]')
    if (action && !action.disabled) send(action.dataset.fleetCommand, action.dataset.key || null)
})
$('back').addEventListener('click', () => send('fleet:back'))

// The window at its minimum size switches the FC to the glance strip. Only re-render when that flips.
let resize_timer = null
fleet_ui.compact = window.innerHeight < COMPACT_HEIGHT
window.addEventListener('resize', () => {
    clearTimeout(resize_timer)
    resize_timer = setTimeout(() => {
        const compact = window.innerHeight < COMPACT_HEIGHT
        if (compact === fleet_ui.compact) return
        fleet_ui.compact = compact
        render_fleet()
    }, 120)
})

// Countdowns and fleet clocks tick locally (text only); the data refreshes from the API. Nothing
// ticks while the window is hidden (EVE not in front, or closed to the tray).
setInterval(() => {
    if (document.hidden || document.body.classList.contains('is-hidden')) return
    document.querySelectorAll('.fleet__countdown').forEach(el => { el.textContent = countdown(el.dataset.start) })
    document.querySelectorAll('#fleet [data-since]').forEach(el => { el.textContent = elapsed(el.dataset.since) })
    document.querySelectorAll('#fleet [data-start]').forEach(el => { el.textContent = until(el.dataset.start) })
}, 1000)


document.querySelectorAll('[data-command]').forEach(button => {
    button.addEventListener('click', () => send(button.dataset.command))
})
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

// Overlay mode is click-through except over controls and rows: tell main when the cursor is over one.
let interactive = false
document.addEventListener('mousemove', event => {
    const over = !!event.target.closest('[data-interactive]')
    if (over !== interactive) {
        interactive = over
        send('mouse:interactive', over)
    }
})
document.addEventListener('mouseleave', () => {
    if (interactive) { interactive = false; send('mouse:interactive', false) }
})

// Bottom-right grip resizes the window (transparent windows have no native resize border).
$('resize').addEventListener('pointerdown', event => {
    $('resize').setPointerCapture(event.pointerId)
    send('resize:start', { x: event.screenX, y: event.screenY })
})
$('resize').addEventListener('pointermove', event => {
    if ($('resize').hasPointerCapture(event.pointerId)) send('resize:move', { x: event.screenX, y: event.screenY })
})
$('resize').addEventListener('pointerup', event => {
    $('resize').releasePointerCapture(event.pointerId)
    send('resize:end')
})
