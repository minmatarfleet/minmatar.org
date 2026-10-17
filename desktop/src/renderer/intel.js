const $ = id => document.getElementById(id)
const { send, on_state, on_visibility } = window.minmatar
window.eve_window.follow_visibility(on_visibility)
const { KIND_LABELS, split_ships, ago, jumps_label, type_icon, image_url, group_by_age } = window.intel_format
const { esc, plural } = window.ui_helpers

const RECENT_ROWS = 4
const RANGES = [3, 5, 10, null]
const AMARR = 500003
const MINMATAR = 500002

let state = null
let view = 'recent'          // 'recent' | 'all' (the draft and report views come from main's state)
let show = 'all'             // Show all filter: 'all' | 'reports' | 'pings'
let detail_tab = 'ships'
let rendered = null          // signature of what #view shows

const in_range = (item, range) => range == null || item.jumps == null || item.jumps <= range

// ---------------------------------------------------------------- rows

function thumb(item, compact) {
    const src = image_url(item.image, 64)
    const img = src ? `<img src="${esc(src)}" alt="">` : '<span class="intel-thumb__blank"></span>'
    const count = !compact && item.count != null && !item.is_ping ? `<span class="intel-thumb__count">${esc(item.count)}</span>` : ''
    return `<span class="intel-thumb${item.is_ping ? ' intel-thumb--ping' : ''}">${img}${count}</span>`
}

function strip(item, index) {
    const { shown, rest, more } = split_ships(item.ships)
    if (!shown.length) return `<span class="intel-row__summary">${esc(item.summary)}</span>`
    const hulls = shown.map(s => `<span class="intel-hull" title="${esc(s.name)}"><img src="${esc(type_icon(s.type_id, 32))}" alt="${esc(s.name)}">×${esc(s.count)}</span>`).join('')
    const pop = rest.length ? `<span class="intel-more-wrap" data-interactive>
            <button class="intel-more" data-action="more" aria-label="${esc(`${more} more ships: ${rest.map(s => `${s.name} ${s.count}`).join(', ')}`)}">+${more}</button>
            <span class="intel-pop${index >= 2 ? ' intel-pop--up' : ''}" role="tooltip">
                <span class="intel-pop__title">${esc(plural(more, 'more ship'))}</span>
                ${rest.map(s => `<span class="intel-pop__row"><img src="${esc(type_icon(s.type_id, 32))}" alt=""><span>${esc(s.name)}</span><span class="intel-num">${esc(s.count)}</span></span>`).join('')}
            </span>
        </span>` : ''
    return `<span class="intel-strip">${hulls}${pop}</span>`
}

// Pings name no source (they all come from the feed), and a fleet ping's summary already starts "Amarr fleet".
function source_line(item) {
    const kind = item.kind === 'fleet' ? '' : `<span class="intel-kind${item.is_ping ? ' intel-kind--ping' : ''}">${esc(KIND_LABELS[item.kind] || item.kind)}</span>`
    const source = item.is_ping ? '' : `${esc(item.source)}${item.note ? ` · “${esc(item.note)}”` : ''}`
    const ships = item.ships && item.ships.length ? esc(item.summary) : ''
    const parts = [kind, source, ships].filter(Boolean)
    return parts.length ? `<span class="intel-row__source">${parts.join(' · ')}</span>` : ''
}

function row(item, index, { compact = false } = {}) {
    const open = item.report_id
        ? `<button class="intel-row__open" data-action="open-report" data-report="${esc(item.report_id)}" aria-label="${esc(`${KIND_LABELS[item.kind]} from ${item.system_name}, open report`)}"></button>`
        : ''
    return `<div class="intel-row${compact ? ' intel-row--compact' : ''}" data-interactive>
        ${open}
        ${thumb(item, compact)}
        <span class="intel-row__text">
            <span class="intel-row__top">
                <span class="intel-row__system">${esc(item.system_name)}</span>
                <span class="intel-meta">${esc(jumps_label(item.jumps))}</span>
                ${item.is_new ? '<span class="intel-new" title="New"></span>' : ''}
                <span class="intel-meta intel-row__ago" data-ago="${esc(item.occurred_at)}">${esc(ago(item.occurred_at))}</span>
            </span>
            ${strip(item, index)}
            ${source_line(item)}
        </span>
    </div>`
}

// ---------------------------------------------------------------- views

function paste_bar(intel) {
    const where = intel.origin ? `in <b>${esc(intel.origin.system)}</b>` : ''
    return `<button class="intel-paste" data-action="paste" data-interactive title="Copy a d-scan or Local member list in EVE, then click here">
        <svg viewBox="0 0 16 16" aria-hidden="true"><path d="M5.5 2.5h-2v12h9v-12h-2M5.5 1.5h5v2.5h-5z"/></svg>
        <span>Paste d-scan or local</span><kbd>Ctrl V</kbd>
        <span class="intel-paste__where">${where}</span>
    </button>`
}

function empty(intel, text) {
    if (intel.error) return `<p class="eve-error">${esc(intel.error)}</p>`
    if (!intel.updated_at) return '<div class="eve-empty">Loading intel…</div>'
    return `<div class="eve-empty">${esc(text)}</div>`
}

function recent_view(intel, items) {
    const shown = items.slice(0, RECENT_ROWS)
    return `${paste_bar(intel)}
    <section aria-label="Recent intel">
        <div class="intel-heading"><span>Recent</span>${items.length ? `<button class="eve-link" data-action="all" data-interactive>Show all ${items.length} →</button>` : ''}</div>
        <div class="intel-list">${shown.length ? shown.map((item, i) => row(item, i)).join('') : empty(intel, 'Nothing in range in the last 2 hours.')}</div>
    </section>`
}

function all_view(intel, items) {
    const counts = { all: items.length, reports: items.filter(i => !i.is_ping).length, pings: items.filter(i => i.is_ping).length }
    const visible = items.filter(i => show === 'all' || (show === 'pings' ? i.is_ping : !i.is_ping))
    const chips = [['all', 'All'], ['reports', 'Reports'], ['pings', 'Pings']].map(([id, label]) =>
        `<button class="intel-chip" data-action="show" data-show="${id}" aria-pressed="${show === id}">${label} <span>${counts[id]}</span></button>`).join('')
    let index = 0
    const groups = group_by_age(visible).map(group => `<section aria-label="${esc(group.title)}">
        <div class="intel-heading"><span>${esc(group.title)}</span><span>${group.items.length}</span></div>
        <div class="intel-list">${group.items.map(item => row(item, index++, { compact: true })).join('')}</div>
    </section>`).join('')
    return `<div class="intel-toolbar" data-interactive>
        <button class="eve-icon-button" data-action="recent" aria-label="Back" title="Back"><svg viewBox="0 0 12 12"><path d="M7.5 2.5L4 6l3.5 3.5"/></svg></button>
        <div class="intel-chips" role="group" aria-label="Show">${chips}</div>
    </div>
    ${groups || empty(intel, 'Nothing here in the last 2 hours.')}
    <p class="intel-hint">Older reports leave this list after 2 hours. Their links keep working.</p>`
}

function draft_preview(draft) {
    if (draft.status === 'loading') return '<div class="eve-empty">Reading the paste…</div>'
    if (!draft.summary) return ''
    if (draft.kind === 'local') {
        // The preview resolves Local like a shared report; without ESI or the cache it can't, and Share tries again.
        if (draft.summary.resolved) return local_summary(draft.summary)
        return `<div class="intel-note">${esc(plural(draft.summary.pilots, 'pilot'))}. Standings couldn't be looked up right now; they're tried again when you share.</div>`
    }
    const s = draft.summary
    const classes = (s.classes || []).slice(0, 3).map(c => `<span><b>${esc(c.count)}</b> ${esc(c.name.toLowerCase())}${c.count === 1 ? '' : 's'}</span>`).join('')
    const top = [...(s.hulls || [])].sort((a, b) => b.count - a.count).slice(0, 6)
    return `<div class="intel-preview-counts">${classes || '<span>No ships</span>'}</div>
        <div class="intel-preview-hulls">${top.map(h => `<figure><img src="${esc(type_icon(h.type_id, 64))}" alt="${esc(h.name)}" title="${esc(h.name)}"><figcaption>×${esc(h.count)}</figcaption></figure>`).join('')}</div>
        <div class="intel-hint intel-hint--left">${esc(`${plural(s.ships, 'ship')} · ${plural(s.capsules, 'capsule')} · ${s.other} other`)}</div>`
}

function draft_view(intel) {
    const d = intel.draft
    if (d.status === 'error' && !d.kind) {
        return `<div class="intel-back" data-interactive><h2>New report</h2></div>
            <p class="eve-error">${esc(d.error)}</p>
            <div class="intel-actions" data-interactive><button class="intel-button" data-action="discard">Close</button><button class="intel-button intel-button--primary" data-action="paste">Paste again</button></div>`
    }
    const shared = d.status === 'shared'
    const tab = kind => `<button class="intel-chip" data-action="kind" data-kind="${kind}" aria-pressed="${d.kind === kind}" ${shared ? 'disabled' : ''}>${kind === 'dscan' ? 'D-scan' : 'Local'}</button>`
    const meta = d.summary ? (d.kind === 'dscan' ? `${plural(d.summary.ships, 'ship')} · ${d.summary.other + d.summary.capsules} other` : plural(d.summary.pilots, 'pilot')) : ''
    return `<div class="intel-back" data-interactive>
            <button class="eve-icon-button" data-action="discard" aria-label="Discard" title="Discard (Esc)"><svg viewBox="0 0 12 12"><path d="M7.5 2.5L4 6l3.5 3.5"/></svg></button>
            <h2>New report</h2>
        </div>
        <div class="intel-form" data-interactive>
            <span>Type</span>
            <span class="intel-toolbar"><span class="intel-chips" role="group" aria-label="Report type">${tab('dscan')}${tab('local')}</span><span class="intel-meta">${d.lines ? `auto-detected · ${plural(d.lines, 'line')}` : ''}</span></span>
            <label for="system">System</label>
            <input id="system" data-field="system" autocomplete="off" spellcheck="false" placeholder="System name" ${shared ? 'disabled' : ''}>
            <label for="note">Note</label>
            <input id="note" data-field="note" autocomplete="off" maxlength="200" placeholder="Optional, e.g. on the Siseide gate" ${shared ? 'disabled' : ''}>
        </div>
        <section class="intel-section" aria-label="Preview">
            <div class="intel-heading"><span>Preview</span><span>${esc(meta)}</span></div>
            ${draft_preview(d)}
        </section>
        ${d.error ? `<p class="eve-error">${esc(d.error)}</p>` : ''}
        <div class="intel-footer-actions" data-interactive>
            ${shared ? `<div class="intel-status" role="status">Shared · link copied<button class="eve-link" data-action="open-report" data-report="${esc(d.report_id)}">View report</button></div>` : ''}
            <div class="intel-actions">
                ${shared
                    ? '<button class="intel-button intel-button--primary" data-action="discard">Done</button>'
                    : `<button class="intel-button" data-action="discard">Discard</button>
                       <button class="intel-button intel-button--primary" data-action="share" ${d.status === 'ready' ? '' : 'disabled'}>${d.status === 'sharing' ? 'Sharing…' : 'Share to intel'}</button>`}
            </div>
            <p class="intel-hint">${shared ? 'Paste the link in fleet chat or Discord.' : 'Enter to share · Esc to discard · visible to alliance members'}</p>
        </div>`
}

function standing_square(side) {
    const glyph = side === 'hostile' ? '<path d="M2 5h6"/>' : side === 'friendly' ? '<path d="M2 5h6M5 2v6"/>' : ''
    return `<span class="intel-standing intel-standing--${esc(side)}" role="img" aria-label="${esc(side)}"><svg viewBox="0 0 10 10" aria-hidden="true">${glyph}</svg></span>`
}

function dscan_detail(r) {
    const s = r.summary
    const tabs = [['ships', `Ships ${s.ships}`], ['other', `Other ${s.other + s.capsules}`], ['raw', 'Raw paste']].map(([id, label]) =>
        `<button class="intel-tab" role="tab" data-action="tab" data-tab="${id}" aria-selected="${detail_tab === id}">${esc(label)}</button>`).join('')
    let body = ''
    if (detail_tab === 'ships') {
        body = (s.classes || []).map(c => `<div class="intel-class">
            <div class="intel-heading"><span>${esc(c.name)}</span><span class="intel-num">${esc(c.count)}</span></div>
            <div class="intel-hull-grid">${c.hulls.map(h => `<div class="intel-hull-cell"><img src="${esc(type_icon(h.type_id, 64))}" alt=""><span>${esc(h.name)}</span><span class="intel-num">${esc(h.count)}</span></div>`).join('')}</div>
        </div>`).join('') || '<div class="eve-empty">No ships on scan.</div>'
    } else if (detail_tab === 'other') {
        const rows = [...(s.capsules ? [{ type_id: 670, name: 'Capsule', group: 'Capsule', count: s.capsules }] : []), ...(s.other_items || [])]
        body = rows.map(o => `<div class="intel-hull-cell"><img src="${esc(type_icon(o.type_id, 64))}" alt=""><span>${esc(o.name)}<br><small class="intel-meta">${esc(o.group)}</small></span><span class="intel-num">${esc(o.count)}</span></div>`).join('') || '<div class="eve-empty">Nothing else on scan.</div>'
    } else {
        body = `<pre class="intel-raw">${esc(r.raw_preview)}${r.raw_lines > 12 ? `\n… ${r.raw_lines - 12} more lines` : ''}</pre>`
    }
    return `<div class="intel-stats">
            <div><b>${esc(s.ships)}</b><span>Ships</span></div>
            <div><b>${esc(s.capsules)}</b><span>Capsules</span></div>
            <div><b>${esc(s.other)}</b><span>Structures, other</span></div>
        </div>
        <div class="intel-tabs" role="tablist" aria-label="Report sections" data-interactive>${tabs}</div>
        <div class="intel-section">${body}</div>`
}

function local_detail(r) {
    const s = r.summary
    if (!s.resolved) return `<div class="intel-note">${esc(plural(s.pilots, 'pilot'))}. Standings couldn't be looked up when this was shared.</div>`
    const delta = r.previous && r.previous.hostile_delta
        ? `<span class="intel-up">${r.previous.hostile_delta > 0 ? '+' : ''}${esc(r.previous.hostile_delta)} hostile</span><span class="intel-meta">since ${esc(new Date(r.previous.created_at).toISOString().slice(11, 16))}</span>`
        : ''
    return local_summary(s, delta)
}

// A resolved Local: standings bar, militia counts and alliances. Shared by the report view and the draft preview.
function local_summary(s, delta = '') {
    const st = s.standings
    const logo = id => `<img src="${esc(image_url({ kind: 'faction', id }, 64))}" alt="">`
    const alliances = (s.alliances || []).map(a => {
        const img = a.id ? `<img class="intel-logo" src="${esc(image_url({ kind: 'alliance', id: a.id }, 64))}" alt="">` : '<span class="intel-logo intel-logo--blank">—</span>'
        return `<div class="intel-alliance">${img}<span>${esc(a.name)}</span>${standing_square(a.standing)}<span class="intel-num">${esc(a.count)}</span></div>`
    }).join('')
    return `<div class="intel-toolbar"><b class="intel-big">${esc(s.pilots)}</b><span class="eve-dim">pilots in local</span><span class="intel-spacer"></span>${delta}</div>
        <div class="intel-bar" role="img" aria-label="${esc(`${st.hostile} hostile, ${st.neutral} neutral, ${st.friendly} friendly`)}">
            <div class="intel-bar__hostile" data-flex="${st.hostile}"></div><div class="intel-bar__neutral" data-flex="${st.neutral}"></div><div class="intel-bar__friendly" data-flex="${st.friendly}"></div>
        </div>
        <div class="intel-stats intel-stats--logos">
            <div>${logo(AMARR)}<span><b>${esc(s.militia.amarr)}</b><br><small>Amarr militia</small></span></div>
            <div><span class="intel-logo intel-logo--blank intel-logo--lg">—</span><span><b>${esc(s.militia.none)}</b><br><small>No militia</small></span></div>
            <div>${logo(MINMATAR)}<span><b>${esc(s.militia.minmatar)}</b><br><small>Minmatar militia</small></span></div>
        </div>
        <section aria-label="By alliance"><div class="intel-heading"><span>By alliance</span>${s.unknown ? `<span>${esc(s.unknown)} not found</span>` : ''}</div>${alliances}</section>`
}

function detail_view(intel) {
    const r = intel.detail
    const back = `<div class="intel-back" data-interactive>
        <button class="eve-icon-button" data-action="close-report" aria-label="Back" title="Back"><svg viewBox="0 0 12 12"><path d="M7.5 2.5L4 6l3.5 3.5"/></svg></button>
        <h2>${esc(r.system_name || 'Report')}</h2><span class="intel-meta">${esc(r.kind === 'local' ? 'Local' : r.kind === 'dscan' ? 'D-scan' : '')}${r.jumps != null ? ` · ${esc(jumps_label(r.jumps))}` : ''}</span>
    </div>`
    if (r.status === 'loading') return `${back}<div class="eve-empty">Loading report…</div>`
    if (r.status === 'error') return `${back}<p class="eve-error">${esc(r.error)}</p>`
    return `${back}
        <div class="intel-byline"><span><b>${esc(r.reporter_name)}</b> · ${esc(ago(r.created_at))} ago · ${esc(new Date(r.created_at).toISOString().slice(11, 16))} EVE</span>${r.note ? `<q>${esc(r.note)}</q>` : ''}</div>
        ${r.kind === 'dscan' ? dscan_detail(r) : local_detail(r)}
        <div class="intel-actions" data-interactive>
            <button class="intel-button intel-button--primary" data-action="copy-link" data-report="${esc(r.report_id)}">Copy link</button>
            <button class="intel-button" data-action="open-site" data-report="${esc(r.report_id)}">Open on site</button>
        </div>`
}

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
        html = () => detail_view(intel)
    } else {
        signature = JSON.stringify([view, show, items, intel.error, !!intel.updated_at, intel.origin])
        html = () => (view === 'all' ? all_view(intel, items) : recent_view(intel, items))
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
