// The Fleets window: three tabs in the title bar (Fleet, Upcoming, Recent) that never go away, a return
// strip back to your live fleet on the other two, and a status bar. The views are fleet_view.js; this file
// keeps the tab, routes clicks to the main process and ticks the clocks.
const $ = id => document.getElementById(id)
const { send, on_state, on_visibility, on_fleet } = window.minmatar
window.eve_window.follow_visibility(on_visibility)
const view = window.fleet_view
const fmt = window.fleet_format

const COMPACT_HEIGHT = 360
const TABS = ['fleet', 'upcoming', 'recent']

let state = null                 // app state (the schedule, update status, pin)
let fleet = null                 // fleet_window.js snapshot
const ui = { tab: 'fleet', fc_view: 'overview', compact: window.innerHeight < COMPACT_HEIGHT }
let shown = null                 // what the body showed last: scroll resets when it changes

// Rewrite a part only when its HTML changed: a poll with nothing new leaves the DOM (and its images) alone.
function patch(el, html) {
    if (el.__html === html) return false
    el.__html = html
    el.innerHTML = html
    el.querySelectorAll('[data-pct]').forEach(bar => { bar.style.width = `${bar.dataset.pct}%` })
    el.querySelectorAll('[data-h]').forEach(bar => { bar.style.height = `${bar.dataset.h}%` })
    return true
}

function render() {
    if (!state || !fleet) return
    const list = state.fleets || []
    const tabs = view.tabs(fleet, list)
    for (const tab of TABS) {
        const on = ui.tab === tab
        const el = $(`tab-${tab}`)
        el.setAttribute('aria-selected', String(on))
        el.tabIndex = on ? 0 : -1
    }
    $('tab-fleet-dot').hidden = !tabs.live
    $('tab-upcoming-count').textContent = tabs.upcoming ? String(tabs.upcoming) : ''
    $('tab-recent-dot').hidden = !tabs.owed

    const parts = ui.tab === 'upcoming' ? view.upcoming_tab(fleet, list)
        : ui.tab === 'recent' ? view.recent_tab(fleet)
        : view.fleet_tab(fleet, ui)
    patch($('strip'), ui.tab === 'fleet' ? '' : view.strip(fleet))
    const where = `${ui.tab}:${fleet.opened ? fleet.opened.id : ''}:${fleet.focus ? fleet.focus.kind : ''}:${ui.fc_view}`
    if (patch($('view'), parts.main) && where !== shown) $('view').scrollTop = 0
    shown = where

    patch($('actions'), parts.actions || '')
    $('foot').classList.toggle('has-actions', !!parts.actions)
    const prompt = window.eve_window.update_prompt(state.update)
    const update = prompt
        ? `<button class="fw-update" data-app-command="${prompt.command}" title="${view.esc(prompt.title)}">${view.esc(prompt.label)}</button>` : ''
    patch($('status'), view.status(fleet, { update }))
    $('site').hidden = !parts.site_id
    if (parts.site_id) $('site').dataset.id = String(parts.site_id)
    document.body.classList.toggle('is-compact', !!parts.compact)
}

function set_tab(tab) {
    if (!TABS.includes(tab)) return
    // Clicking Upcoming while a fleet is open goes back to the list.
    if (tab === 'upcoming' && ui.tab === 'upcoming' && fleet && fleet.opened) send('fleet:close')
    ui.tab = tab
    render()
}

on_state(next => {
    state = next
    window.eve_window.apply(state)
    $('refresh').classList.toggle('is-loading', !!state.loading)
    render()
})

on_fleet(snapshot => {
    const before = fleet
    fleet = snapshot || { loaded: false, focus: { kind: 'none' }, signups: {}, reminders: [] }
    // The window comes to the Fleet tab when you join a fleet or your sign-up forms, unless you are reading
    // a fleet you opened. It never moves you otherwise.
    const joined = fleet.live && !(before && before.live && before.live.id === fleet.live.id)
    const formed = fleet.focus && fleet.focus.kind === 'formup' && !(before && before.focus && before.focus.kind === 'formup')
    if ((joined || formed) && !(ui.tab === 'upcoming' && fleet.opened)) ui.tab = 'fleet'
    // Opening the fleet you are in shows it where it lives.
    if (fleet.opened && fleet.opened.is_current) {
        ui.tab = 'fleet'
        send('fleet:close')
    }
    render()
})

// One click handler for everything the views draw.
document.addEventListener('click', event => {
    const target = event.target.closest('[data-tab], [data-view], [data-open], [data-close], [data-fleet-command], [data-app-command]')
    if (!target || target.disabled) return
    if (target.dataset.tab) return set_tab(target.dataset.tab)
    if (target.dataset.view) {
        ui.fc_view = target.dataset.view
        return render()
    }
    if (target.dataset.open) {
        const id = Number(target.dataset.open)
        if (fleet && fleet.live && fleet.live.id === id) return set_tab('fleet')
        ui.tab = 'upcoming'
        render()
        return send('fleet:open', id)
    }
    if ('close' in target.dataset) return send('fleet:close')
    if (target.dataset.appCommand) return send(target.dataset.appCommand)
    const command = target.dataset.fleetCommand
    const id = target.dataset.id ? Number(target.dataset.id) : undefined
    send(command, target.dataset.key ? { fleet_id: id, key: target.dataset.key } : id)
})

// Arrow keys move between the title-bar tabs (one tab stop, as a tablist should be).
$('tab-fleet').parentElement.addEventListener('keydown', event => {
    if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return
    event.preventDefault()
    const i = TABS.indexOf(ui.tab)
    const next = event.key === 'Home' ? 0 : event.key === 'End' ? TABS.length - 1
        : (i + (event.key === 'ArrowRight' ? 1 : TABS.length - 1)) % TABS.length
    set_tab(TABS[next])
    $(`tab-${TABS[next]}`).focus()
})

// The window at its minimum size switches the FC to the glance strip. Only re-render when that flips.
let resize_timer = null
window.addEventListener('resize', () => {
    clearTimeout(resize_timer)
    resize_timer = setTimeout(() => {
        const compact = window.innerHeight < COMPACT_HEIGHT
        if (compact === ui.compact) return
        ui.compact = compact
        render()
    }, 120)
})

// Clocks tick locally (text only); the data refreshes from the API. Nothing ticks while the window is
// hidden (EVE not in front, or closed to the tray).
setInterval(() => {
    if (document.hidden || document.body.classList.contains('is-hidden')) return
    document.querySelectorAll('[data-since]').forEach(el => { el.textContent = view.elapsed(el.dataset.since) })
    document.querySelectorAll('[data-clock]').forEach(el => {
        const c = fmt.clock(el.dataset.clock)
        el.textContent = c.text
        el.classList.toggle('is-started', c.started)
    })
}, 1000)

window.eve_window.wire_overlay(send)
