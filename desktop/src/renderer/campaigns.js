const $ = id => document.getElementById(id)
const { send, on_state, on_visibility } = window.minmatar
window.eve_window.follow_visibility(on_visibility)
const { eve_time } = window.fleet_format
const { activity_text, ago_text } = window.campaign_format
const { content } = window.campaign_view

let rendered = null   // signature of what the window currently shows
let pilots = []       // the pilots behind the faces, for the tooltip

// The page's CSP has no inline styles, so bar geometry goes on through the CSSOM.
function apply_geometry(root) {
    root.querySelectorAll('[data-width]').forEach(el => {
        el.style.left = `${el.dataset.left}%`
        el.style.width = `${el.dataset.width}%`
    })
}

on_state(state => {
    window.eve_window.apply(state)
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
    if (state.campaign) pilots = state.campaign.pilots
    $('content').innerHTML = content(state)
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
