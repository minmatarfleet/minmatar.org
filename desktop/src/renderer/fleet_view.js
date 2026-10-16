// The fleet view of the Fleets window: FC summary, member view, form-up, ship lost, after-action.
// Pure functions from the main process's fleet snapshot (src/main/fleet_window.js) to HTML for each
// part of the window (top, main, foot). fleets.js only rewrites a part whose HTML changed, so a poll
// that brings nothing new touches no DOM, and ship icons are never reloaded.
// No inline styles (the window's CSP is style-src 'self'): bar widths ride in data-pct and fleets.js
// applies them. Shared by the window (global `fleet_view`) and the node tests (module.exports).
(function (root) {
    const IMAGES = 'https://images.evetech.net'
    const ROLE_LABELS = { logi: 'Logi', links: 'Links', cyno: 'Cyno' }
    const ATTENTION_LABELS = { capsule: 'In a pod', off_doctrine: 'Off doctrine', docked: 'Docked', away: 'Not with the fleet' }
    const pad = n => String(n).padStart(2, '0')

    const esc = value => String(value == null ? '' : value).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]))

    // One image URL per type (64 px, crisp at 2x for the 24-32 px icons) so the cache serves every use.
    const ship_icon = (type_id, size, extra = '') => type_id
        ? `<img class="fw-icon" src="${IMAGES}/types/${Number(type_id)}/icon?size=64" alt="" width="${size}" height="${size}" decoding="async"${extra}>`
        : `<span class="fw-icon fw-s${size}"></span>`
    const portrait = (character_id, size) => character_id
        ? `<img class="fw-portrait" src="${IMAGES}/characters/${Number(character_id)}/portrait?size=64" alt="" width="${size}" height="${size}" decoding="async">`
        : `<span class="fw-portrait fw-s${size}"></span>`

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

    function eve_clock(iso) {
        const d = new Date(iso)
        return `${pad(d.getUTCHours())}:${pad(d.getUTCMinutes())}`
    }

    function duration(seconds) {
        const h = Math.floor(seconds / 3600), m = Math.floor((seconds % 3600) / 60)
        return h ? `${h}h ${pad(m)}m` : `${m}m`
    }

    const plural = (n, one, many = `${one}s`) => `${n} ${n === 1 ? one : many}`

    const button = (command, label, { primary = false, key = null, disabled = false } = {}) =>
        `<button class="eve-button${primary ? ' eve-button--primary' : ''} fw-button" data-interactive data-fleet-command="${command}"${key ? ` data-key="${esc(key)}"` : ''}${disabled ? ' disabled' : ''}>${esc(label)}</button>`
    const link = (command, label) => `<button class="eve-link" data-interactive data-fleet-command="${command}">${esc(label)}</button>`
    const section = (label, aside = '') => `<div class="fw-section"><span>${esc(label)}</span>${aside ? `<span class="fw-section__aside">${esc(aside)}</span>` : ''}</div>`
    const live_clock = since => `<span class="fw-live" data-since="${esc(since)}">${elapsed(since)}</span>`

    // ------------------------------------------------------------ FC, live

    function fc_top(s, tab) {
        const f = s.fleet, c = s.counts
        return `<div class="fw-id"><span class="fw-title">${esc(f.title)}</span>${live_clock(f.started_at)}</div>
            <div class="fw-meta">${esc(f.type_label)}${f.fc_system_name ? ` · ${esc(f.fc_system_name)}` : ''} · you are FC</div>
            <div class="fw-stats">
                <div><span class="fw-stat">${c.in_fleet}</span><span>in fleet</span></div>
                <div><span class="fw-stat">${c.with_fc}</span><span>with you</span></div>
                <div><span class="fw-stat">${c.kills}<span class="fw-stat__sep"> / </span>${c.losses}</span><span>kills / losses</span></div>
            </div>
            <div class="fw-tabs" role="tablist" aria-label="Fleet view">
                <button role="tab" data-interactive data-tab="summary" aria-selected="${tab === 'summary'}">Summary</button>
                <button role="tab" data-interactive data-tab="pilots" aria-selected="${tab === 'pilots'}">Pilots</button>
            </div>`
    }

    function roles_line(roles) {
        if (!roles.length) return ''
        return `<div class="fw-roles">${roles.map(r => r.covered
            ? `<span>${ROLE_LABELS[r.role] || esc(r.role)} ✓</span>`
            : `<span class="fw-warn">No ${(ROLE_LABELS[r.role] || esc(r.role)).toLowerCase()}</span>`).join('')}</div>`
    }

    function fc_summary(s) {
        const ships = s.ships.map(ship => `<div class="fw-row">
                ${ship_icon(ship.ship_type_id, 24)}
                <span class="fw-row__name">${esc(ship.ship_name)}</span>
                <span class="fw-count${ship.flying < ship.signed_up ? ' fw-warn' : ''}">${ship.flying}<span class="fw-stat__sep"> / </span>${ship.signed_up}</span>
            </div>`).join('')
        const people = s.attention.reduce((n, group) => n + group.names.length, 0)
        const attention = s.attention.map(group => `<div class="fw-attention fw-attention--${esc(group.reason)}">
                <span class="fw-dot" aria-hidden="true"></span>
                <span class="fw-row__name"><span class="fw-attention__label">${esc(ATTENTION_LABELS[group.reason] || group.reason)}</span> <span class="eve-dim">${esc(group.names.join(', '))}</span></span>
            </div>`).join('')
        return (s.ships.length ? section('Doctrine', 'flying / signed up') + ships + roles_line(s.roles) : '')
            + section('Needs attention', people ? plural(people, 'pilot') : '')
            + (attention || '<div class="fw-quiet">Everyone is in a doctrine ship with the fleet.</div>')
    }

    function fc_pilots(s) {
        const groups = []
        for (const pilot of s.pilots) {
            let group = groups.find(g => g.system === pilot.solar_system_name)
            if (!group) groups.push(group = { system: pilot.solar_system_name, here: pilot.solar_system_id === s.fleet.fc_system_id, pilots: [] })
            group.pilots.push(pilot)
        }
        return groups.map(group => section(`${group.system}${group.here ? ' · with you' : ''}`, String(group.pilots.length))
            + group.pilots.map(p => {
                const tag = p.capsule ? '<span class="fw-tag fw-danger">in pod</span>'
                    : !p.doctrine && s.ships.length ? '<span class="fw-tag fw-warn">off doctrine</span>'
                    : p.docked ? '<span class="fw-tag">docked</span>' : ''
                return `<div class="fw-pilot">
                    ${portrait(p.character_id, 22)}
                    <span class="fw-row__name">${esc(p.character_name)}</span>
                    ${tag}
                    <span title="${esc(p.ship_name)}">${ship_icon(p.ship_type_id, 22, ` title="${esc(p.ship_name)}"`)}</span>
                </div>`
            }).join('')).join('') || '<div class="fw-quiet">Nobody in fleet yet.</div>'
    }

    function fc_foot(s) {
        return `${button('fleet:refresh-motd', s.busy === 'motd' ? 'Refreshing…' : 'Refresh MOTD', { primary: true, disabled: !!s.busy })}
            ${link('fleet:open-site', 'Open on site')}`
    }

    // Window at its minimum size: the count, the doctrine bars and one line for who needs a nudge.
    function fc_compact(s) {
        const c = s.counts
        const people = s.attention.reduce((n, group) => n + group.names.length, 0)
        const gaps = s.roles.filter(r => !r.covered).map(r => `no ${(ROLE_LABELS[r.role] || r.role).toLowerCase()}`)
        const reasons = s.attention.map(g => `${g.names.length} ${(ATTENTION_LABELS[g.reason] || g.reason).toLowerCase()}`).concat(gaps)
        const bars = s.ships.map(ship => {
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

    // ------------------------------------------------------------ member, live

    function header_fc(s, right) {
        const f = s.fleet
        return `<div class="fw-id fw-id--fc">
                ${portrait(f.fc_character_id, 36)}
                <span class="fw-title">${esc(f.title)}</span>
                ${right}
                <span class="fw-meta">${f.fc_name ? `FC ${esc(f.fc_name)}` : 'No FC'}${s.counts && f.live ? ` · ${plural(s.counts.in_fleet, 'pilot')}` : ''}</span>
            </div>`
    }

    function where_line(s) {
        const f = s.fleet
        const system = f.fc_system_name || f.location_system_name || ''
        if (s.jumps === 0) return { text: `With the fleet in ${system}`, warn: false }
        if (s.jumps == null) return { text: system ? `Fleet is in ${system}` : 'Fleet location unknown', warn: false }
        return { text: `${plural(s.jumps, 'jump')} behind · fleet is in ${system}`, warn: true }
    }

    function fits(s, { copy = true } = {}) {
        return s.ships.map(ship => `<div class="fw-row">
                ${ship_icon(ship.ship_type_id, 24)}
                <span class="fw-row__name">${esc(ship.ship_name)} <span class="eve-dim">${esc(ship.role_label)}</span></span>
                ${copy ? button('fleet:copy-fit', 'Copy', { key: ship.key }) : ''}
            </div>`).join('')
    }

    function member_main(s) {
        const you = s.you
        const where = where_line(s)
        const ship_line = !you ? ''
            : you.capsule ? '<span class="fw-danger">In a capsule</span>'
            : you.doctrine ? '<span class="eve-dim">✓ Doctrine ship</span>'
            : s.ships.length ? '<span class="fw-warn">Not a doctrine ship</span>' : ''
        const needs = s.needs.map(n => n.kind === 'ship'
            ? `<span class="fw-chip">${ship_icon(n.ship_type_id, 22)}${n.count} ${esc(n.label)}</span>`
            : `<span class="fw-chip fw-chip--text">${n.count} ${esc((ROLE_LABELS[n.label] || n.label).toLowerCase())}</span>`).join('')
        return `<div class="fw-card">
                ${you ? `<div class="fw-you">${ship_icon(you.ship_type_id, 48)}<span class="fw-you__ship">${esc(you.ship_name)}</span>${ship_line}</div>` : ''}
                <div class="fw-where${where.warn ? ' fw-warn' : ''}">${esc(where.text)}</div>
            </div>
            ${needs ? section('Fleet needs') + `<div class="fw-chips">${needs}</div>` : ''}
            ${s.ships.length ? section('Doctrine fits') + fits(s) : ''}`
    }

    // ------------------------------------------------------------ form-up / not in the fleet

    function formup_top(s) {
        const f = s.fleet
        const right = f.live ? live_clock(f.started_at)
            : f.start_time ? `<span class="fw-countdown" data-start="${esc(f.start_time)}">${until(f.start_time)}</span>` : ''
        return `<div class="fw-id"><span class="fw-title">${esc(f.title)}</span>${right}</div>
            <div class="fw-meta">${f.live ? 'Live' : f.start_time ? `Starts ${eve_clock(f.start_time)} EVE` : ''}${f.fc_name ? ` · FC ${esc(f.fc_name)}` : ''}</div>`
    }

    function formup_main(s) {
        const f = s.fleet
        const place = f.live ? f.fc_system_name : (f.location_name || f.location_system_name)
        const jumps = s.jumps == null ? '' : s.jumps === 0 ? ' · you are here' : ` · ${plural(s.jumps, 'jump')}`
        const picked = s.ships.find(ship => ship.key === s.signed_up_key)
        const rows = s.ships.map(ship => {
            const on = ship.key === s.signed_up_key
            return `<button class="fw-pick${on ? ' is-on' : ''}" role="radio" aria-checked="${on}" data-interactive data-fleet-command="fleet:sign-up" data-key="${esc(ship.key)}"${s.busy ? ' disabled' : ''}>
                ${ship_icon(ship.ship_type_id, 32)}
                <span class="fw-row__name">${esc(ship.ship_name)} <span class="eve-dim">${esc(ship.role_label)}</span></span>
                <span class="fw-count eve-dim">${ship.signed_up}</span>
            </button>`
        }).join('')
        return `${place ? `<div class="fw-card fw-where${s.jumps ? ' fw-warn' : ''}">${f.live ? 'Fleet is in' : 'Form up in'} ${esc(place)}${esc(jumps)}</div>` : ''}
            ${s.ships.length ? section('What will you fly?', 'signed up') + `<div role="radiogroup" aria-label="Pick your ship">${rows}</div>` : '<div class="fw-quiet">No doctrine set yet. Ask the FC.</div>'}
            ${picked ? `<div class="fw-picked"><span class="eve-dim">Signed up as ${esc(picked.ship_name)}</span>${button('fleet:copy-fit', 'Copy fit', { key: picked.key })}</div>` : ''}`
    }

    // ------------------------------------------------------------ ship lost / after-action

    function banner(type_id, kicker, title, line, tone = '') {
        return `<div class="fw-banner${tone ? ` fw-banner--${tone}` : ''}">
                ${type_id ? `<img class="fw-banner__render" src="${IMAGES}/types/${Number(type_id)}/render?size=256" alt="" decoding="async">` : ''}
                <div class="fw-banner__text">
                    ${kicker ? `<span class="fw-banner__kicker">${esc(kicker)}</span>` : ''}
                    <span class="fw-title">${esc(title)}</span>
                    <span class="fw-meta">${esc(line)}</span>
                </div>
            </div>`
    }

    function loss_top(s) {
        const loss = s.loss
        return banner(loss.ship_type_id, 'Ship lost', loss.ship_name, `${loss.solar_system_name} · ${isk(loss.isk_value)} ISK · ${eve_clock(loss.killmail_time)} EVE`, 'loss')
    }

    function loss_main(s) {
        const place = s.fleet.location_name || s.fleet.location_system_name
        return `${s.loss.srp_filed
                ? '<div class="fw-card fw-action"><span>SRP filed for this loss</span></div>'
                : `<div class="fw-card fw-action"><span>File SRP <span class="eve-dim">· copies the killmail link</span></span>${button('fleet:srp', 'File now', { primary: true })}</div>`}
            ${place ? `<div class="fw-card fw-action"><span>Reship at ${esc(place)}</span></div>` : ''}`
    }

    function after_top(s) {
        const f = s.fleet, a = s.after_action
        return banner(s.ships[0] && s.ships[0].ship_type_id, '', f.title, `Ended ${eve_clock(f.ended_at)} EVE · ${duration(a.duration_seconds)} · ${plural(a.pilots, 'pilot')}`)
    }

    function after_main(s) {
        const c = s.counts, a = s.after_action
        const total = c.isk_destroyed + c.isk_lost
        const pct = total ? Math.round(c.isk_destroyed / total * 100) : 0
        const items = []
        if (!a.aar_link) items.push(`<div class="fw-action"><span>Link the AAR <span class="eve-dim">· no thread yet</span></span>${button('fleet:open-site', 'Add link', { primary: true })}</div>`)
        if (a.losses) items.push(`<div class="fw-action"><span>SRP <span class="eve-dim">· ${a.srp_filed} of ${plural(a.losses, 'loss', 'losses')} filed</span></span>${link('fleet:open-site', 'Review')}</div>`)
        return `<div class="fw-stats fw-stats--two">
                <div><span class="fw-stat">${isk(c.isk_destroyed)}</span><span>destroyed · ${plural(c.kills, 'ship')}</span></div>
                <div><span class="fw-stat">${isk(c.isk_lost)}</span><span>lost · ${plural(c.losses, 'ship')}</span></div>
            </div>
            ${total ? `<div class="fw-efficiency" role="img" aria-label="ISK efficiency ${pct} percent"><span class="fw-efficiency__bar"><span data-pct="${pct}"></span></span><span class="eve-dim">${pct}%</span></div>` : ''}
            ${items.length ? section('Wrap up') + items.join('') : ''}`
    }

    // ------------------------------------------------------------ entry point

    // { title, top, main, foot } for the current snapshot. ui = { tab, compact }.
    function render(s, ui = {}) {
        const notice = s.notice ? `<span class="fw-notice" role="status">${esc(s.notice)}</span>` : ''
        const site = link('fleet:open-site', 'Open on site')
        if (s.view === 'loading') return { title: 'Fleet', top: '', main: '<div class="fw-quiet">Loading…</div>', foot: '' }
        if (s.view === 'loss') return { title: 'Fleet', top: loss_top(s), main: loss_main(s), foot: `${notice}${button('fleet:dismiss-loss', 'Back to fleet')}` }
        if (s.view === 'after') return { title: 'After-action', top: after_top(s), main: after_main(s), foot: `${button('fleet:done', 'Done')}${link('fleet:open-site', 'Full report')}${notice}` }
        if (s.mode === 'fc' && s.fleet.live) {
            if (ui.compact) return { title: s.fleet.title, top: '', main: fc_compact(s), foot: notice }
            const tab = ui.tab === 'pilots' ? 'pilots' : 'summary'
            return { title: 'Fleet', top: fc_top(s, tab), main: tab === 'pilots' ? fc_pilots(s) : fc_summary(s), foot: `${fc_foot(s)}${notice}` }
        }
        if (s.mode === 'member' && s.fleet.live) {
            return { title: 'Fleet', top: header_fc(s, live_clock(s.fleet.started_at)), main: member_main(s), foot: `<span class="eve-dim">${esc(s.you ? s.you.character_name : '')}</span>${notice}${site}` }
        }
        return { title: s.fleet.live ? 'Fleet' : 'Form-up', top: formup_top(s), main: formup_main(s), foot: `${notice}${site}` }
    }

    const api = { render, isk, elapsed, until, esc }
    if (typeof module !== 'undefined' && module.exports) module.exports = api
    else root.fleet_view = api
})(this)
