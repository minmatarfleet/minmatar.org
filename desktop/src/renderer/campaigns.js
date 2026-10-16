const $ = id => document.getElementById(id)
const { send, on_state, on_visibility } = window.minmatar
window.eve_window.follow_visibility(on_visibility)
const { eve_time } = window.fleet_format
const { change_tone, change_text, bar, activity_text, ago_text } = window.campaign_format
const esc = value => String(value == null ? '' : value).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]))

const STACK_FACES = 5   // faces shown before "+N" when the window is narrow (campaigns.css)
const HOLDERS = { minmatar: 'Held by Minmatar', amarr: 'Held by Amarr' }
const ARROWS = {
    up: '<svg viewBox="0 0 12 12" aria-hidden="true"><path d="M6 2l5 8H1z"/></svg>',
    down: '<svg viewBox="0 0 12 12" aria-hidden="true"><path d="M6 10l5-8H1z"/></svg>',
    steady: '<svg viewBox="0 0 12 12" aria-hidden="true"><path d="M1.5 6h9"/></svg>',
    none: '',
}
const CHANGE_WORDS = { up: 'gaining', down: 'losing', steady: 'steady', none: 'no reading yet' }

let rendered = null   // signature of what the window currently shows
let pilots = []       // the pilots behind the faces, for the tooltip

function render_system(system) {
    const tone = change_tone(system.change)
    const geometry = bar(system.progress, system.change)
    const holder = system.holder
        ? `<img class="system__holder" src="../assets/${system.holder}.svg" alt="${HOLDERS[system.holder]}" title="${HOLDERS[system.holder]}">`
        : '<span class="system__holder"></span>'
    const label = `${system.name}, ${system.objective}, ${CHANGE_WORDS[tone]} ${change_text(system.change)} in 24 hours`
    return `<div class="system" role="link" tabindex="0" data-interactive data-open title="${esc(system.detail)}" aria-label="${esc(label)}">
        ${holder}
        <span class="system__names"><span class="system__name">${esc(system.name)}</span><span class="system__objective">${esc(system.objective)}</span></span>
        <span class="meter" aria-hidden="true">
            <span class="meter__fill" data-left="0" data-width="${geometry.fill}"></span>
            <span class="meter__delta meter__delta--${tone}" data-left="${geometry.delta_from}" data-width="${geometry.delta_width}"></span>
        </span>
        <span class="change change--${tone}" aria-hidden="true">${ARROWS[tone]}${change_text(system.change)}</span>
    </div>`
}

function render_pilots(campaign) {
    pilots = campaign.pilots
    if (!pilots.length) return '<p class="pilots-empty">Nobody has flown this campaign in the last hour.</p>'
    const faces = pilots.map((pilot, i) =>
        `<button class="pilot" data-interactive data-pilot="${i}" aria-label="${esc(`${pilot.name}: ${activity_text(pilot)}`)}">
            <img src="https://images.evetech.net/characters/${encodeURIComponent(pilot.character_id)}/portrait?size=64" alt="">
        </button>`).join('')
    const more = pilots.length - STACK_FACES
    return `<div class="pilots">${faces}
        <span class="pilots__more" ${more > 0 ? '' : 'hidden'} aria-hidden="true">+${Math.max(0, more)}</span>
        <span class="pilots__label">${pilots.length} active in the last hour</span>
    </div>`
}

function render_skeleton() {
    return '<div class="campaign-heading"><span class="skeleton skeleton--short"></span></div>' +
        Array.from({ length: 3 }, () => '<div class="system system--skeleton" aria-hidden="true"><span></span><span class="skeleton"></span><span class="skeleton"></span><span></span></div>').join('')
}

function render(state) {
    const campaign = state.campaign
    if (!campaign) {
        if (!state.campaign_updated_at && !state.campaign_error) return render_skeleton()
        return state.campaign_error ? '' : '<div class="eve-empty">No campaign is live right now.</div>'
    }
    const count = campaign.pilots.length
    return `<section class="campaign-group" aria-label="Systems">
            <div class="campaign-heading"><span>Systems</span><span class="eve-dim">Week ${campaign.week_index} of ${campaign.week_count}</span></div>
            ${campaign.systems.map(render_system).join('')}
        </section>
        <section class="campaign-group" aria-label="Active in the last hour">
            <div class="campaign-heading"><span>Active in the last hour</span><span class="eve-dim">${count} ${count === 1 ? 'pilot' : 'pilots'}</span></div>
            ${render_pilots(campaign)}
        </section>`
}

// The page's CSP has no inline styles, so bar geometry goes on through the CSSOM.
function apply_geometry(root) {
    root.querySelectorAll('[data-width]').forEach(el => {
        el.style.left = `${el.dataset.left}%`
        el.style.width = `${el.dataset.width}%`
    })
}

on_state(state => {
    window.eve_window.apply(state)
    $('overlay').setAttribute('aria-pressed', String(state.overlay))
    $('refresh').classList.toggle('is-loading', state.loading)
    $('title').textContent = state.campaign ? state.campaign.name : 'Campaigns'
    $('status').textContent = state.campaign_updated_at ? `Updated ${eve_time(state.campaign_updated_at)} EVE` : ''
    $('open-site').hidden = !state.campaign
    $('version').textContent = `v${state.version}`
    const update = state.update || {}
    $('update').hidden = !['ready', 'available'].includes(update.status)
    $('update').textContent = update.status === 'ready' ? `Restart to update (v${update.version})` : `v${update.version} available`
    $('update').dataset.action = update.status === 'ready' ? 'update:install' : 'update:download'

    // State is pushed on every focus change; only rebuild when the content changed so portraits don't flicker.
    const signature = JSON.stringify([state.campaign, state.campaign_error, !!state.campaign_updated_at])
    if (signature === rendered) return
    rendered = signature
    hide_tip()
    $('content').innerHTML = (state.campaign_error ? `<p class="eve-error">${esc(state.campaign_error)}</p>` : '') + render(state)
    apply_geometry($('content'))
})

// ---------------------------------------------------------------- pilot tooltip

function show_tip(face) {
    const pilot = pilots[Number(face.dataset.pilot)]
    if (!pilot) return
    $('tip-name').textContent = pilot.name
    $('tip-activity').textContent = activity_text(pilot)
    $('tip-when').textContent = [pilot.system, ago_text(pilot.last_at)].filter(Boolean).join(' · ')
    const tip = $('tip')
    tip.hidden = false
    // Above the face, kept inside the window.
    const face_box = face.getBoundingClientRect()
    const width = tip.offsetWidth
    const left = Math.min(Math.max(4, face_box.left), window.innerWidth - width - 4)
    tip.style.left = `${left}px`
    tip.style.top = `${Math.max(4, face_box.top - tip.offsetHeight - 6)}px`
}

function hide_tip() {
    $('tip').hidden = true
}

$('content').addEventListener('mouseover', event => {
    const face = event.target.closest('[data-pilot]')
    if (face) show_tip(face)
})
$('content').addEventListener('mouseout', event => {
    const face = event.target.closest('[data-pilot]')
    if (face && !face.contains(event.relatedTarget)) hide_tip()
})
$('content').addEventListener('focusin', event => {
    const face = event.target.closest('[data-pilot]')
    if (face) show_tip(face)
})
$('content').addEventListener('focusout', hide_tip)
$('content').addEventListener('scroll', hide_tip)

// ---------------------------------------------------------------- actions

window.eve_window.wire_overlay(send)
$('update').addEventListener('click', () => send($('update').dataset.action))

$('content').addEventListener('click', event => {
    if (event.target.closest('[data-open]')) send('campaigns:open')
})
$('content').addEventListener('keydown', event => {
    if (event.target.closest('[data-open]') && (event.key === 'Enter' || event.key === ' ')) {
        event.preventDefault()
        send('campaigns:open')
    }
})
