const $ = id => document.getElementById(id)
const { send, on_state, on_visibility } = window.minmatar
window.eve_window.follow_visibility(on_visibility)
const { ago } = window.intel_format
const { in_range, recent_view, all_view, draft_view, detail_view } = window.intel_view

const RANGES = [3, 5, 10, null]

let state = null
let view = 'recent'          // 'recent' | 'all' (the draft and report views come from main's state)
let show = 'all'             // Show all filter: 'all' | 'reports' | 'pings'
let detail_tab = 'ships'
let rendered = null          // signature of what #view shows

// ---------------------------------------------------------------- render

function render() {
    const intel = state && state.intel
    if (!intel) return
    const items = intel.items.filter(item => in_range(item, intel.range))
    let html, signature
    if (intel.draft) {
        // Inputs keep what the pilot typed; only the draft's status and preview re-render the form.
        const { system, note, system_edited, ...rest } = intel.draft
        signature = JSON.stringify(['draft', rest])
        html = () => draft_view(intel)
    } else if (intel.detail) {
        signature = JSON.stringify(['detail', intel.detail, detail_tab])
        html = () => detail_view(intel, detail_tab)
    } else {
        signature = JSON.stringify([view, show, items, intel.error, !!intel.updated_at, intel.origin])
        html = () => (view === 'all' ? all_view(intel, items, show) : recent_view(intel, items))
    }
    if (signature === rendered) return
    const was_draft = rendered && rendered.startsWith('["draft"')
    const keep = was_draft && intel.draft ? { system: $('system') && $('system').value, note: $('note') && $('note').value } : null
    const focused = document.activeElement && document.activeElement.id
    rendered = signature
    $('view').innerHTML = html()
    capture_wheel()
    // The page's CSP allows no inline styles; sizes that come from data are set through the CSSOM.
    document.querySelectorAll('[data-flex]').forEach(el => { el.style.flex = el.dataset.flex })
    if (intel.draft && $('system')) {
        $('system').value = keep ? keep.system : (intel.draft.system || '')
        $('note').value = keep ? keep.note : (intel.draft.note || '')
        const target = keep ? $(focused) : (intel.draft.system ? $('note') : $('system'))
        if (target && !target.disabled) target.focus()
    }
}

// Click-through hands the mouse wheel to EVE as well, so a report or a list that scrolls takes the whole view.
function capture_wheel() {
    const intel = state && state.intel
    const view = $('view')
    view.toggleAttribute('data-interactive', !!(intel && (intel.draft || intel.detail)) || view.scrollHeight > view.clientHeight)
}
new ResizeObserver(capture_wheel).observe($('view'))

on_state(next => {
    state = next
    window.eve_window.apply(state)
    // The range comes from main (intel.js DEFAULT_RANGE until the pilot picks one); hidden until the map loads.
    const intel = state.intel || { items: [] }
    if (state.intel) $('range').textContent = intel.range == null ? 'Any distance' : `Within ${intel.range} jumps`
    $('range').hidden = !intel.map_ready
    $('status').textContent = intel.error ? 'Offline' : intel.updated_at ? 'Live' : 'Connecting…'
    $('status').classList.toggle('is-error', !!intel.error)
    $('version').textContent = `v${state.version}`
    window.eve_window.show_update($('update'), state.update)
    render()
})

// "12m" labels age between refreshes.
setInterval(() => {
    document.querySelectorAll('[data-ago]').forEach(el => { el.textContent = ago(el.dataset.ago) })
}, 30_000)

// ---------------------------------------------------------------- input

document.addEventListener('click', event => {
    const target = event.target.closest('[data-action]')
    if (!target) return
    const { action } = target.dataset
    if (action === 'paste') send('intel:paste')
    else if (action === 'all' || action === 'recent') { view = action; render() }
    else if (action === 'show') { show = target.dataset.show; render() }
    else if (action === 'kind') send('intel:kind', target.dataset.kind)
    else if (action === 'share') share()
    else if (action === 'discard') send('intel:discard')
    else if (action === 'open-report') { detail_tab = 'ships'; send('intel:discard'); send('intel:open-report', target.dataset.report) }
    else if (action === 'close-report') send('intel:close-report')
    else if (action === 'tab') { detail_tab = target.dataset.tab; rendered = null; render() }
    else if (action === 'copy-link') { send('intel:copy-link', target.dataset.report); target.textContent = 'Link copied' }
    else if (action === 'open-site') send('intel:open-site', target.dataset.report)
    else if (action === 'more') target.parentElement.classList.toggle('is-open')
})

function share() {
    send('intel:edit', { system: $('system').value, note: $('note').value })
    send('intel:share')
}

document.addEventListener('input', event => {
    const field = event.target.dataset && event.target.dataset.field
    if (field) send('intel:edit', { [field]: event.target.value })
})

document.addEventListener('keydown', event => {
    const draft = state && state.intel && state.intel.draft
    if (!draft) return
    if (event.key === 'Escape') { event.preventDefault(); send('intel:discard') }
    else if (event.key === 'Enter' && draft.status === 'ready') { event.preventDefault(); share() }
})

// Ctrl+V while the window has focus (unpinned, or while writing a report). Outside the form's fields.
document.addEventListener('paste', event => {
    if (event.target.closest && event.target.closest('input')) return
    const text = event.clipboardData && event.clipboardData.getData('text')
    if (text) { event.preventDefault(); send('intel:paste-text', text) }
})

$('range').addEventListener('click', () => {
    if (!state || !state.intel) return
    send('intel:range', RANGES[(RANGES.indexOf(state.intel.range) + 1) % RANGES.length])
})

window.eve_window.wire_overlay(send)
window.eve_window.wire_update($('update'), send)
