// The Fleets window's three tabs as HTML: Fleet (the fleet you are in, its loss card and wrap-up, the
// form-up of a sign-up that formed without you, the FC's pre-flight, or your next fleet), Upcoming (the
// schedule and one fleet opened from it) and Recent (SRP you still owe, your last fleets). Plus the return
// strip shown on the other tabs while you are in a live fleet, and the status bar.
//
// Pure functions from the main process's snapshot (src/main/fleet_window.js). fleets.js only rewrites a
// part whose HTML changed, so a poll that brings nothing new touches no DOM and ship icons never reload.
// No inline styles (the window's CSP is style-src 'self'): bar widths ride in data-pct. Clocks carry their
// time in data-clock / data-since and fleets.js ticks them. Shared by the window (global `fleet_view`) and
// the node tests (module.exports).
(function (root) {
    const node = typeof module !== 'undefined' && module.exports
    const fmt = node ? require('./fleet_format') : root.fleet_format
    const { esc, plural, type_icon, type_render, portrait: portrait_url } = node ? require('./ui_helpers') : root.ui_helpers
    const ROLE_LABELS = { logi: 'Logi', links: 'Links', cyno: 'Cyno' }
    const ATTENTION_LABELS = {
        capsule: 'In a pod', off_doctrine: 'Off doctrine', docked: 'Docked', away: 'Not with the fleet', not_in_fleet: 'Signed up, not in fleet',
    }
    const SRP_LABELS = { none: 'SRP not filed', pending: 'SRP pending', approved: 'SRP paid', rejected: 'SRP rejected' }
    const pad = n => String(n).padStart(2, '0')

    // One image URL per type (64 px, crisp at 2x for the 20-48 px icons) so the cache serves every use.
    const ship_icon = (type_id, size, extra = '') => type_id
        ? `<img class="fw-icon" src="${type_icon(Number(type_id))}" alt="" width="${size}" height="${size}" decoding="async"${extra}>`
        : `<span class="fw-icon fw-s${size}"></span>`
    const portrait = (character_id, size) => character_id
        ? `<img class="fw-portrait" src="${portrait_url(Number(character_id))}" alt="" width="${size}" height="${size}" decoding="async">`
        : `<span class="fw-portrait fw-s${size}"></span>`
    const render_img = type_id => type_id
        ? `<img class="fw-render" src="${type_render(Number(type_id))}" alt="" decoding="async">` : ''

    function isk(value) {
        const n = Number(value) || 0
        if (n >= 1e9) return `${(n / 1e9).toFixed(2)}B`
        if (n >= 1e6) return `${Math.round(n / 1e6)}M`
        if (n >= 1e3) return `${Math.round(n / 1e3)}K`
        return String(n)
    }

    function elapsed(since, now = new Date(), { seconds = true } = {}) {
        const s = Math.max(0, Math.floor((now - new Date(since)) / 1000))
        const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60)
        return seconds ? `${h}:${pad(m)}:${pad(s % 60)}` : `${h}:${pad(m)}`
    }

    function until(start, now = new Date()) {
        const s = Math.max(0, Math.round((new Date(start) - now) / 1000))
        const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60)
        return h ? `${h}:${pad(m)}:${pad(s % 60)}` : `${m}:${pad(s % 60)}`
    }

    const eve_clock = fmt.eve_time

    function duration(seconds) {
        const h = Math.floor(seconds / 3600), m = Math.floor((seconds % 3600) / 60)
        return h ? `${h}h ${pad(m)}m` : `${m}m`
    }

    const fit_label = name => String(name || '').replace(/^\[[^\]]*\]\s*/, '')
    const fleet_title = row => row.doctrine || `${row.type_label} fleet`

    // ------------------------------------------------------------ small parts

    // Every clickable thing is a real button carrying its command and the ids it acts on.
    function button(command, label, { primary = false, quiet = false, id = null, key = null, disabled = false, aria = null, title = null } = {}) {
        const cls = primary ? ' eve-button--primary' : quiet ? ' fw-button--quiet' : ''
        return `<button class="eve-button fw-button${cls}" data-interactive data-fleet-command="${command}"${id != null ? ` data-id="${Number(id)}"` : ''}${key ? ` data-key="${esc(key)}"` : ''}${disabled ? ' disabled' : ''}${aria ? ` aria-label="${esc(aria)}"` : ''}${title ? ` title="${esc(title)}"` : ''}>${esc(label)}</button>`
    }
    const section = (label, aside = '', tone = '') => `<div class="fw-section${tone ? ` fw-section--${tone}` : ''}"><span>${esc(label)}</span>${aside ? `<span class="fw-section__aside">${esc(aside)}</span>` : ''}</div>`
    const live_clock = since => `<span class="fw-live" data-since="${esc(since)}">${elapsed(since)}</span>`
    // The fleet clock: HH:MM:SS to the start, then fleet-red and counting up (fleets.js ticks it).
    const fleet_clock = (iso, big = false) => {
        const c = fmt.clock(iso)
        return `<span class="fw-clock${big ? ' fw-clock--big' : ''}${c.started ? ' is-started' : ''}" data-clock="${esc(iso)}">${esc(c.text)}</span>`
    }
    // EVE time and the pilot's local time together; local is coloured by their hour, with the word for it.
    const when = iso => {
        const local = fmt.local_time(iso)
        return `<span class="fw-when">${eve_clock(iso)} EVE <span class="fw-local ${local.band}" title="${local.word}">${local.text} local</span></span>`
    }
    const destination_button = (system_id, label = 'Set destination') => system_id
        ? button('fleet:destination', label, { id: system_id, aria: `${label} in EVE` }) : ''

    // ------------------------------------------------------------ Fleet tab: member, live

    function fleet_header(v, right) {
        const f = v.fleet, c = v.counts
        const bits = [f.fc_name ? `FC ${f.fc_name}` : 'No FC', f.type_label]
        if (f.live && c) bits.push(plural(c.in_fleet, 'pilot'), `${c.kills} kills / ${c.losses} lost`)
        return `<section class="fw-head" aria-label="Fleet">
                ${portrait(f.fc_character_id, 36)}
                <span class="fw-title">${esc(f.title)}</span>
                ${right}
                <span class="fw-meta">${esc(bits.join(' · '))}</span>
            </section>`
    }

    function loss_card(v) {
        const loss = v.loss, f = v.fleet
        const srp = loss.srp_filed
            ? '<span class="fw-done">SRP filed ✓</span>'
            : button('fleet:srp', 'File SRP', { primary: true, id: loss.killmail_id })
        const reship = f.location_system_id
            ? button('fleet:destination', `Reship in ${f.location_system_name || 'staging'}`, { id: f.location_system_id }) : ''
        return `<section class="fw-loss" aria-label="Ship lost">
                ${render_img(loss.ship_type_id)}
                <div class="fw-loss__head">
                    <div class="fw-loss__text">
                        <span class="fw-kicker fw-danger">Ship lost · ${eve_clock(loss.killmail_time)} EVE</span>
                        <span class="fw-loss__ship">${esc(loss.ship_name)}</span>
                        <span class="fw-meta">${esc(loss.solar_system_name)} · ${isk(loss.isk_value)} ISK${loss.srp_filed ? '' : ' · killmail ready for SRP'}</span>
                    </div>
                    <button class="eve-icon-button fw-close" data-interactive data-fleet-command="fleet:dismiss-loss" data-id="${Number(loss.killmail_id)}" aria-label="Close. SRP stays in Recent" title="Close. SRP stays in Recent"><svg viewBox="0 0 12 12" aria-hidden="true"><path d="M2.5 2.5l7 7M9.5 2.5l-7 7"/></svg></button>
                </div>
                <div class="fw-loss__actions">${srp}${reship}</div>
            </section>`
    }

    function where_line(v) {
        const f = v.fleet
        const system = f.fc_system_name || f.location_system_name || ''
        if (v.jumps === 0) return { text: `With the fleet in ${system}`, warn: false }
        if (v.jumps == null) return { text: system ? `Fleet is in ${system}` : 'Fleet location unknown', warn: false }
        return { text: `${plural(v.jumps, 'jump')} behind · fleet is in ${system}`, warn: true }
    }

    function fits(v) {
        return v.ships.map(ship => `<div class="fw-row">
                ${ship_icon(ship.ship_type_id, 24)}
                <span class="fw-row__name">${esc(ship.ship_name)} <span class="eve-dim">${esc(ship.role_label)}</span></span>
                ${button('fleet:copy-fit', 'Copy', { quiet: true, id: v.fleet.id, key: ship.key, aria: `Copy ${ship.ship_name} fit` })}
            </div>`).join('')
    }

    function needs_chips(v) {
        return v.needs.map(n => n.kind === 'ship'
            ? `<span class="fw-chip">${ship_icon(n.ship_type_id, 22)}${n.count} ${esc(n.label)}</span>`
            : `<span class="fw-chip fw-chip--text">${n.count} ${esc((ROLE_LABELS[n.label] || n.label).toLowerCase())}</span>`).join('')
    }

    function member_main(v) {
        const you = v.you, f = v.fleet
        const where = where_line(v)
        const ship_line = !you ? ''
            : you.capsule ? '<span class="fw-danger">In a pod · reship, then come back</span>'
            : you.doctrine ? '<span class="eve-dim">✓ Doctrine ship</span>'
            : v.ships.length ? '<span class="fw-warn">Not a doctrine ship</span>' : ''
        const needs = needs_chips(v)
        const route = v.jumps === 0 ? '' : destination_button(f.fc_system_id)
        return `${fleet_header(v, live_clock(f.started_at))}
            ${v.loss ? loss_card(v) : ''}
            <div class="fw-card">
                ${you ? `<div class="fw-you">${ship_icon(you.ship_type_id, 44)}<span class="fw-you__ship">${esc(you.ship_name)}</span><span class="fw-you__who">${esc(you.character_name)}</span>${ship_line}</div>` : ''}
                <div class="fw-where${where.warn ? ' fw-warn' : ''}"><span>${esc(where.text)}</span>${route}</div>
            </div>
            ${needs ? section('Fleet needs') + `<div class="fw-chips">${needs}</div>` : ''}
            ${v.ships.length ? section('Doctrine fits', 'EFT to clipboard') + fits(v) : ''}`
    }

    // ------------------------------------------------------------ Fleet tab: FC, live

    function fc_head(v, view) {
        const f = v.fleet, c = v.counts
        const chip = (key, label, aside = '') => `<button role="tab" data-interactive data-view="${key}" aria-selected="${view === key}">${esc(label)}${aside ? ` <span class="eve-dim">${esc(aside)}</span>` : ''}</button>`
        return `<section class="fw-fc-head" aria-label="Your fleet">
                <div class="fw-id"><span class="fw-title">${esc(f.title)}</span>${live_clock(f.started_at)}</div>
                <div class="fw-meta">${esc(f.type_label)}${f.fc_system_name ? ` · ${esc(f.fc_system_name)}` : ''} · you are FC</div>
                <div class="fw-stats">
                    <div><span class="fw-stat">${c.in_fleet}</span><span>in fleet</span></div>
                    <div><span class="fw-stat">${c.with_fc}</span><span>with you</span></div>
                    <div><span class="fw-stat">${c.kills}<span class="fw-stat__sep"> / </span>${c.losses}</span><span>kills / losses</span></div>
                </div>
                <div class="fw-chipbar" role="tablist" aria-label="Fleet detail">
                    ${chip('overview', 'Overview')}${chip('pilots', 'Pilots', String(c.in_fleet))}${chip('kills', 'Kills', `${c.kills} / ${c.losses}`)}
                </div>
            </section>`
    }

    function roles_line(roles) {
        if (!roles.length) return ''
        return `<div class="fw-roles">${roles.map(r => r.covered
            ? `<span>${ROLE_LABELS[r.role] || esc(r.role)} ✓</span>`
            : `<span class="fw-warn">No ${(ROLE_LABELS[r.role] || esc(r.role)).toLowerCase()}</span>`).join('')}</div>`
    }

    function fc_overview(v) {
        const ships = v.ships.map(ship => `<div class="fw-row">
                ${ship_icon(ship.ship_type_id, 24)}
                <span class="fw-row__name">${esc(ship.ship_name)}</span>
                <span class="fw-count${ship.flying < ship.signed_up ? ' fw-warn' : ''}">${ship.flying}<span class="fw-stat__sep"> / </span>${ship.signed_up}</span>
            </div>`).join('')
        const people = v.attention.reduce((n, group) => n + group.names.length, 0)
        const attention = v.attention.map(group => `<div class="fw-attention fw-attention--${esc(group.reason)}">
                <span class="fw-dot" aria-hidden="true"></span>
                <span class="fw-row__name"><span class="fw-attention__label">${esc(ATTENTION_LABELS[group.reason] || group.reason)}</span> <span class="eve-dim">${esc(group.names.join(', '))}</span></span>
            </div>`).join('')
        return (v.ships.length ? section('Doctrine', 'flying / signed up') + ships + roles_line(v.roles) : '')
            + section('Needs a nudge', people ? plural(people, 'pilot') : '')
            + (attention || '<div class="fw-quiet">Everyone is in a doctrine ship with the fleet.</div>')
    }

    function fc_pilots(v) {
        const groups = []
        for (const pilot of v.pilots) {
            let group = groups.find(g => g.system === pilot.solar_system_name)
            if (!group) groups.push(group = { system: pilot.solar_system_name, here: pilot.solar_system_id === v.fleet.fc_system_id, pilots: [] })
            group.pilots.push(pilot)
        }
        return groups.map(group => section(`${group.system}${group.here ? ' · with you' : ''}`, String(group.pilots.length))
            + group.pilots.map(p => {
                const tag = p.capsule ? '<span class="fw-tag fw-danger">in pod</span>'
                    : !p.doctrine && v.ships.length ? '<span class="fw-tag fw-warn">off doctrine</span>'
                    : p.docked ? '<span class="fw-tag">docked</span>' : '<span></span>'
                return `<div class="fw-pilot">
                    ${portrait(p.character_id, 22)}
                    <span class="fw-row__name">${esc(p.character_name)}</span>
                    ${tag}
                    <span title="${esc(p.ship_name)}">${ship_icon(p.ship_type_id, 22, ` title="${esc(p.ship_name)}"`)}</span>
                </div>`
            }).join('')).join('') || '<div class="fw-quiet">Nobody in fleet yet.</div>'
    }

    function isk_summary(c) {
        const total = c.isk_destroyed + c.isk_lost
        const pct = total ? Math.round(c.isk_destroyed / total * 100) : 0
        return `<div class="fw-stats fw-stats--two">
                <div><span class="fw-stat">${isk(c.isk_destroyed)}</span><span>destroyed · ${plural(c.kills, 'ship')}</span></div>
                <div><span class="fw-stat">${isk(c.isk_lost)}</span><span>lost · ${plural(c.losses, 'ship')}</span></div>
            </div>
            ${total ? `<div class="fw-efficiency" role="img" aria-label="ISK efficiency ${pct} percent"><span class="fw-efficiency__bar"><span data-pct="${pct}"></span></span><span class="eve-dim">${pct}%</span></div>` : ''}`
    }

    function fc_kills(v) {
        const rows = v.feed.map(k => {
            const loss = k.outcome === 'loss'
            const who = loss ? k.victim_name : `${k.solar_system_name}`
            const sub = loss ? `${k.solar_system_name} · ${k.capsule ? 'pod' : 'ship'} lost` : `${plural(k.fleet_pilots, 'pilot')} on it${k.victim_name ? ` · ${k.victim_name}` : ''}`
            return `<div class="fw-kill${loss ? ' fw-kill--loss' : ''}">
                <span class="fw-kill__time">${eve_clock(k.killmail_time)}</span>
                ${ship_icon(k.ship_type_id, 26)}
                <span class="fw-kill__text"><span><span class="${loss ? 'fw-danger' : 'fw-good'}">${loss ? 'Loss' : 'Kill'}</span> <span class="fw-row__name">${esc(k.ship_name || 'Unknown')}</span></span><span class="fw-meta">${esc(loss ? `${who} · ${k.solar_system_name}` : sub)}</span></span>
                <span class="fw-count">${isk(k.isk_value)}</span>
            </div>`
        }).join('')
        return `<div class="fw-gap"></div>${isk_summary(v.counts)}${section('Newest first', 'EVE time')}${rows || '<div class="fw-quiet">No kills or losses yet.</div>'}`
    }

    // Window at its minimum size: the count, the doctrine bars and one line for who needs a nudge.
    function fc_compact(v) {
        const c = v.counts
        const people = v.attention.reduce((n, group) => n + group.names.length, 0)
        const gaps = v.roles.filter(r => !r.covered).map(r => `no ${(ROLE_LABELS[r.role] || r.role).toLowerCase()}`)
        const reasons = v.attention.map(g => `${g.names.length} ${(ATTENTION_LABELS[g.reason] || g.reason).toLowerCase()}`).concat(gaps)
        const bars = v.ships.map(ship => {
            const pct = ship.signed_up ? Math.min(100, Math.round(ship.flying / ship.signed_up * 100)) : 100
            const short = ship.flying < ship.signed_up
            return `<div class="fw-bar-row">
                ${ship_icon(ship.ship_type_id, 20)}
                <span class="fw-bar"><span class="${short ? 'fw-bar--short' : ''}" data-pct="${pct}"></span></span>
                <span class="fw-count${short ? ' fw-warn' : ''}">${ship.flying}/${ship.signed_up}</span>
            </div>`
        }).join('')
        return `<div class="fw-compact-count"><span class="fw-stat fw-stat--big">${c.in_fleet}</span><span class="eve-dim">in fleet · ${c.with_fc} with you</span><span class="fw-compact-kl">${c.kills} / ${c.losses}</span></div>
            <div class="fw-bars">${bars}</div>
            ${people || gaps.length ? `<div class="fw-compact-alert"><span class="fw-warn">!</span> <span>${people ? plural(people, 'pilot') + ' need attention' : 'Roles missing'}</span> <span class="eve-dim">${esc(reasons.join(' · '))}</span></div>` : ''}`
    }

    // ------------------------------------------------------------ Fleet tab: wrap-up, form-up, pre-flight, next

    function wrapup_main(v, next) {
        const f = v.fleet, a = v.after_action
        const items = []
        if (!a.aar_link) items.push(`<div class="fw-action"><span>Link the AAR <span class="eve-dim">· no thread yet</span></span>${button('fleet:open-site', 'Add link', { primary: true, id: f.id })}</div>`)
        if (a.losses) items.push(`<div class="fw-action"><span>SRP <span class="eve-dim">· ${a.srp_filed} of ${plural(a.losses, 'loss', 'losses')} filed</span></span>${button('fleet:open-site', 'Review', { quiet: true, id: f.id })}</div>`)
        return `<section class="fw-card fw-wrap" aria-label="Fleet ended">
                <div class="fw-banner">${render_img(v.ships[0] && v.ships[0].ship_type_id)}
                    <div class="fw-banner__text">
                        <span class="fw-kicker">Fleet ended · ${eve_clock(f.ended_at)} EVE</span>
                        <span class="fw-title">${esc(f.title)}</span>
                        <span class="fw-meta">${duration(a.duration_seconds)} · ${plural(a.pilots, 'pilot')} · you were FC</span>
                    </div>
                </div>
                <div class="fw-wrap__body">
                    ${isk_summary(v.counts)}
                    ${items.length ? section('Wrap up', `${items.length} left`, 'warn') + items.join('') : ''}
                    <div class="fw-wrap__done">${button('fleet:done', 'Done, move to Recent')}</div>
                </div>
            </section>
            ${next ? section('Your next fleet') + next_card(next) : ''}`
    }

    function step(n, title, sub, action = '', done = false) {
        return `<div class="fw-step">
                <span class="fw-step__n${done ? ' is-done' : ''}" aria-hidden="true">${done ? '✓' : n}</span>
                <span class="fw-step__title">${title}</span>
                <span class="fw-step__action">${action}</span>
                <span class="fw-meta">${sub}</span>
            </div>`
    }

    function picked_ship(v) {
        return v.ships.find(ship => ship.key === v.signed_up_key) || null
    }

    function formup_main(v) {
        const f = v.fleet
        const picked = picked_ship(v)
        const place_id = f.live ? f.fc_system_id : f.location_system_id
        const place = f.live ? f.fc_system_name : (f.location_system_name || f.location_name)
        const jumps = v.jumps == null ? '' : v.jumps === 0 ? 'you are there' : `<span class="fw-warn">${plural(v.jumps, 'jump')}</span> from you`
        const needs = needs_chips(v)
        const clock = f.live ? live_clock(f.started_at) : fleet_clock(f.start_time)
        return `${fleet_header(v, clock)}
            <div class="fw-card">
                <div class="fw-card__head"><span class="fw-card__title">You're not in the fleet yet</span><span class="fw-meta">${v.you ? esc(v.you.character_name) : 'Signed up'}${picked ? ` · as ${esc(picked.ship_name)}` : ''}</span></div>
                ${step(1, `Get to ${esc(place || 'the fleet')}`, jumps || esc(f.location_name || ''), v.jumps === 0 ? '' : destination_button(place_id), v.jumps === 0)}
                ${step(2, picked ? `Board a ${esc(picked.ship_name)}` : 'Pick a ship', picked ? 'fit to clipboard' : 'from the doctrine below',
                    picked ? button('fleet:copy-fit', 'Copy fit', { quiet: true, id: f.id, key: picked.key }) : '')}
                ${step(3, 'X up for an invite', `Fleet chat in game${f.fc_name ? ` · FC ${esc(f.fc_name)}` : ''}`)}
            </div>
            ${needs ? section('Fleet needs') + `<div class="fw-chips">${needs}</div>` : ''}
            ${picked ? '' : picks(v)}`
    }

    function check(ok, label, sub, action = '') {
        return `<div class="fw-check">
                <span class="fw-check__mark${ok ? ' is-ok' : ''}" aria-hidden="true">${ok ? '✓' : ''}</span>
                <span class="fw-row__name">${esc(label)} <span class="${ok ? 'eve-dim' : 'fw-warn'}">${esc(sub)}</span></span>
                ${action}
            </div>`
    }

    function prep_main(v) {
        const f = v.fleet
        const signed = v.ships.reduce((n, ship) => n + ship.signed_up, 0)
        const checks = [
            check(!!f.doctrine_name, 'Doctrine', f.doctrine_name || 'not set'),
            check(!!f.location_name, 'Form-up', f.location_name || 'not set'),
            check(v.prepinged, 'Discord pre-ping', v.prepinged ? 'sent' : 'not sent from here',
                v.prepinged ? '' : button('fleet:preping', 'Send pre-ping', { quiet: true, id: f.id })),
        ]
        const ready = [!!f.doctrine_name, !!f.location_name, v.prepinged].filter(Boolean).length
        const most = Math.max(1, ...v.ships.map(ship => ship.signed_up))
        const ships = v.ships.map(ship => `<div class="fw-hull">
                ${ship_icon(ship.ship_type_id, 24)}
                <span class="fw-row__name">${esc(ship.ship_name)} <span class="eve-dim">${esc(ship.role_label)}</span></span>
                <span class="fw-bar"><span data-pct="${Math.round(ship.signed_up / most * 100)}"></span></span>
                <span class="fw-count">${ship.signed_up}</span>
            </div>`).join('')
        return `<section class="fw-fc-head" aria-label="Your fleet">
                <div class="fw-id"><span class="fw-title">${esc(f.title)}</span>${fleet_clock(f.start_time, true)}</div>
                <div class="fw-meta">${esc(f.type_label)} · ${when(f.start_time)} · you are FC</div>
            </section>
            ${section('Ready to start', `${ready} of 3`)}
            ${checks.join('')}
            ${v.ships.length ? section('Signed up', plural(signed, 'pilot')) + ships + roles_line(v.roles) : '<div class="fw-quiet">No doctrine set yet.</div>'}`
    }

    function next_card(row, signup = null) {
        return `<button class="fw-next" data-interactive data-open="${Number(row.id)}">
                ${portrait(row.fc_character_id, 36)}
                <span class="fw-next__title">${esc(fleet_title(row))}</span>
                ${fleet_clock(row.start_time)}
                <span class="fw-meta">${when(row.start_time)} · FC ${esc(row.fc_name)}</span>
                ${signup ? `<span class="fw-next__signed">Signed up as ${esc(fit_label(signup.fit_name) || 'a fit')}</span>` : ''}
            </button>`
    }

    // ------------------------------------------------------------ Fleet tab

    // { main, actions, site_id } for the Fleet tab. ui = { fc_view, compact }.
    function fleet_tab(s, ui = {}) {
        const focus = s.focus || { kind: 'none' }
        const v = focus.fleet
        if (!s.loaded && !v) return { main: '<div class="fw-quiet">Loading…</div>', actions: '', site_id: null }
        if (focus.kind === 'current' && v) {
            if (v.mode === 'fc') {
                if (ui.compact) return { main: fc_compact(v), actions: '', site_id: v.fleet.id, compact: true }
                const view = ['pilots', 'kills'].includes(ui.fc_view) ? ui.fc_view : 'overview'
                const body = view === 'pilots' ? fc_pilots(v) : view === 'kills' ? fc_kills(v) : fc_overview(v)
                return {
                    main: `${v.loss ? loss_card(v) : ''}${fc_head(v, view)}${body}`,
                    actions: button('fleet:refresh-motd', s.busy === 'motd' ? 'Refreshing…' : 'Refresh MOTD', { primary: true, disabled: !!s.busy }),
                    site_id: v.fleet.id,
                }
            }
            return { main: member_main(v), actions: '', site_id: v.fleet.id }
        }
        if (focus.kind === 'wrapup' && v) return { main: wrapup_main(v, s.next), actions: '', site_id: v.fleet.id }
        if (focus.kind === 'formup') return v ? { main: formup_main(v), actions: '', site_id: v.fleet.id } : loading(focus.id)
        if (focus.kind === 'prep') {
            if (!v) return loading(focus.id)
            return {
                main: prep_main(v),
                actions: start_button(s, v),
                site_id: v.fleet.id,
            }
        }
        const next = s.next
        const signup = next && s.signups ? s.signups[next.id] : null
        return {
            main: `<div class="fw-idle"><span class="fw-card__title">You're not in a fleet</span><span class="fw-meta">This fills in by itself when one of your characters joins a fleet, or a fleet you signed up for forms.</span></div>
                ${next ? section(signup ? 'Your next fleet' : 'Next fleet') + next_card(next, signup) : '<div class="fw-quiet">No fleets scheduled.</div>'}
                <button class="eve-link fw-more" data-interactive data-tab="upcoming">See all upcoming fleets</button>`,
            actions: '',
            site_id: next ? next.id : null,
        }
    }

    // Start tracking: the API reads the FC's in-game fleet over ESI and pings Discord.
    const start_button = (s, v) => button('fleet:start', s.busy === 'start' ? 'Starting…' : 'Start fleet', {
        primary: true, id: v.fleet.id, disabled: !!s.busy, title: 'Tracks your in-game fleet and pings Discord',
    })

    const loading = id => ({ main: '<div class="fw-quiet">Loading…</div>', actions: '', site_id: id || null })

    // ------------------------------------------------------------ Upcoming tab

    function list_row(row, s) {
        const live_is_mine = s.live && s.live.id === row.id
        const signup = s.signups ? s.signups[row.id] : null
        const tag = live_is_mine ? '<span class="fw-tag fw-good">you are in</span>'
            : signup ? '<span class="fw-tag fw-gold">signed up</span>'
            : (s.reminders || []).includes(row.id) ? '<span class="fw-tag">reminder on</span>'
            : row.status === 'cancelled' ? '<span class="fw-tag fw-danger">cancelled</span>' : '<span></span>'
        const right = row.live ? '<span class="fw-live-tag">● Live</span>' : fleet_clock(row.start_time)
        return `<button class="fw-list-row${row.status === 'cancelled' ? ' is-cancelled' : ''}" data-interactive data-open="${Number(row.id)}">
                ${portrait(row.fc_character_id, 32)}
                <span class="fw-row__name">${esc(fleet_title(row))} <span class="fleet-type fleet-type--${esc(row.type)}">${esc(row.type_label)}</span></span>
                ${right}
                <span class="fw-meta">${row.live ? 'Live now' : when(row.start_time)} · FC ${esc(row.fc_name)}${row.location ? ` · ${esc(row.location)}` : ''}</span>
                ${tag}
            </button>`
    }

    function list_main(s, list) {
        if (!list.length) return s.loaded === false ? '<div class="fw-quiet">Loading…</div>' : '<div class="fw-quiet">No fleets scheduled.</div>'
        return fmt.group_by_day(list).map(group =>
            section(group.label, String(group.fleets.length), group.label === 'Live now' ? 'live' : '')
            + group.fleets.map(row => list_row(row, s)).join('')).join('')
    }

    function picks(v) {
        if (!v.ships.length) return '<div class="fw-quiet">No doctrine set yet. Ask the FC.</div>'
        const rows = v.ships.map(ship => {
            const on = ship.key === v.signed_up_key
            return `<button class="fw-pick${on ? ' is-on' : ''}" role="radio" aria-checked="${on}" data-interactive data-fleet-command="fleet:sign-up" data-id="${Number(v.fleet.id)}" data-key="${esc(ship.key)}">
                ${ship_icon(ship.ship_type_id, 28)}
                <span class="fw-row__name">${esc(ship.ship_name)} <span class="eve-dim">${esc(ship.role_label)}</span></span>
                <span class="fw-count eve-dim">${ship.signed_up}</span>
            </button>`
        }).join('')
        return section('What will you fly?', 'signed up') + `<div role="radiogroup" aria-label="Pick your ship">${rows}</div>`
    }

    function detail_main(s) {
        const o = s.opened
        const row = o.row
        const v = o.fleet
        const title = v ? v.fleet.title : row ? fleet_title(row) : 'Fleet'
        const crumb = `<nav class="fw-crumb" aria-label="Breadcrumb"><button class="fw-crumb__back" data-interactive data-close aria-label="Back to upcoming fleets"><svg viewBox="0 0 12 12" aria-hidden="true"><path d="M7.5 2.5L4 6l3.5 3.5"/></svg>Upcoming</button><span class="fw-crumb__sep">/</span><span class="fw-crumb__here">${esc(title)}</span></nav>`
        if (!v) return crumb + '<div class="fw-quiet">Loading…</div>'
        if (v.mode === 'fc' && !v.fleet.live) return crumb + prep_main(v)
        const f = v.fleet
        const picked = picked_ship(v)
        const place = f.location_name || f.location_system_name
        const jumps = v.jumps == null ? '' : v.jumps === 0 ? ' · you are here' : ` · ${plural(v.jumps, 'jump')} from you`
        return `${crumb}
            ${fleet_header(v, f.live ? live_clock(f.started_at) : fleet_clock(f.start_time))}
            <div class="fw-meta fw-detail-when">${f.live ? 'Live now' : when(f.start_time)}</div>
            ${place ? `<div class="fw-card"><div class="fw-where"><span>Form up in ${esc(place)}<span class="eve-dim">${esc(jumps)}</span></span>${v.jumps === 0 ? '' : destination_button(f.live ? f.fc_system_id : f.location_system_id)}</div></div>` : ''}
            ${picks(v)}
            ${picked ? `<div class="fw-picked"><span class="eve-dim">Signed up as ${esc(picked.ship_name)}</span>${button('fleet:copy-fit', 'Copy fit', { quiet: true, id: f.id, key: picked.key })}</div>` : ''}
            ${f.live ? '' : `<button class="fw-toggle" role="switch" aria-checked="${v.reminder}" data-interactive data-fleet-command="fleet:remind" data-id="${Number(f.id)}"><span class="fw-toggle__box" aria-hidden="true"></span>Remind me 15 min before form-up</button>`}`
    }

    function upcoming_tab(s, list) {
        if (s.opened) {
            const v = s.opened.fleet
            const prep = v && v.mode === 'fc' && !v.fleet.live
            return {
                main: detail_main(s),
                actions: prep ? start_button(s, v) : '',
                site_id: s.opened.id,
            }
        }
        return { main: list_main(s, list), actions: '', site_id: null }
    }

    // ------------------------------------------------------------ Recent tab

    function recent_tab(s) {
        if (!s.recent) return { main: '<div class="fw-quiet">Loading your recent fleets…</div>', actions: '', site_id: null }
        const owed = []
        for (const f of s.recent.fleets) for (const loss of f.my_losses) if (loss.srp_status === 'none') owed.push({ f, loss })
        const owed_html = owed.map(({ f, loss }) => `<div class="fw-owed">
                ${ship_icon(loss.ship_type_id, 32)}
                <span class="fw-row__name">File SRP · ${esc(loss.ship_name)}</span>
                ${button('fleet:srp', 'File SRP', { primary: true, id: loss.killmail_id })}
                <span class="fw-meta">${esc(f.title)} · ${esc(loss.solar_system_name)} · ${isk(loss.isk_value)} ISK · ${esc(fmt.day_label(loss.killmail_time))}</span>
            </div>`).join('')
        const rows = s.recent.fleets.map(f => {
            const srp = f.my_losses.length
                ? f.my_losses.map(l => SRP_LABELS[l.srp_status] + (l.srp_status === 'approved' && l.srp_amount ? ` ${isk(l.srp_amount)}` : '')).join(' · ')
                : ''
            const srp_tone = f.my_losses.some(l => l.srp_status === 'none') ? 'fw-warn' : f.my_losses.every(l => l.srp_status === 'approved') ? 'fw-good' : 'eve-dim'
            const length = f.ended_at ? duration(Math.round((new Date(f.ended_at) - new Date(f.started_at)) / 1000)) : 'live'
            return `<button class="fw-recent" data-interactive data-fleet-command="fleet:open-site" data-id="${Number(f.fleet_id)}" title="Open on my.minmatar.org">
                <span class="fw-row__name">${esc(f.title)}</span>
                <span class="fw-count">${plural(f.kills, 'kill')} · ${f.losses} lost</span>
                <span class="fw-meta">${esc(fmt.day_label(f.started_at))} · ${esc(length)}${f.was_fc ? ' · you were FC' : ''}${f.my_losses.length ? ` · you lost ${f.my_losses.length}` : ''}</span>
                <span class="fw-tag ${srp_tone}">${esc(srp)}</span>
            </button>`
        }).join('')
        return {
            main: `${owed.length ? section('Needs you', '', 'warn') + owed_html : ''}
                ${section('Your last fleets', 'last 30 days')}
                ${rows || '<div class="fw-quiet">No fleets in the last 30 days.</div>'}`,
            actions: '',
            site_id: null,
        }
    }

    // ------------------------------------------------------------ chrome

    // Shown on Upcoming and Recent while you are in a live fleet: the way back, and what matters about you.
    function strip(s) {
        const live = s.live
        if (!live) return ''
        const note = live.mode === 'fc' ? '<span class="eve-dim">you are FC</span>'
            : live.you && live.you.capsule ? '<span class="fw-danger">in a pod</span>'
            : live.jumps ? `<span class="fw-warn">${plural(live.jumps, 'jump')} behind</span>` : ''
        return `<button class="fw-strip" data-interactive data-tab="fleet" aria-label="Back to your live fleet, ${esc(live.title)}">
                <span class="fw-strip__dot" aria-hidden="true"></span>
                <span class="fw-strip__title">${esc(live.title)}</span>
                <span class="fw-live fw-live--bare" data-since="${esc(live.started_at)}">${elapsed(live.started_at)}</span>
                ${note}
                <span class="fw-strip__back">Back to fleet ›</span>
            </button>`
    }

    // The status bar's message: a confirmation replaces the sync line for a moment, never sits beside it.
    function status(s, { update = null } = {}) {
        if (s.notice) return `<span class="fw-status fw-status--notice" role="status"><svg viewBox="0 0 12 12" aria-hidden="true"><path d="M2.5 6.5l2.2 2.2 4.8-5.2"/></svg>${esc(s.notice)}</span>`
        if (s.error) return `<span class="fw-status fw-status--error" role="status">${esc(s.error)}</span>`
        const synced = s.synced_at ? `Synced ${eve_clock(s.synced_at)} EVE` : s.loaded ? 'Synced' : 'Connecting…'
        return `<span class="fw-status"><span class="fw-status__dot" aria-hidden="true"></span>${synced}</span>${update || ''}`
    }

    function tabs(s, list) {
        return {
            live: !!s.live,
            upcoming: list.filter(f => f.status !== 'cancelled').length,
            owed: !!(s.recent && s.recent.srp_owed),
        }
    }

    const api = {
        fleet_tab, upcoming_tab, recent_tab, strip, status, tabs,
        isk, elapsed, until, esc, fit_label,
    }
    if (typeof module !== 'undefined' && module.exports) module.exports = api
    else root.fleet_view = api
})(this)
