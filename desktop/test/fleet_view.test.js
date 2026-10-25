const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('fs')
const path = require('path')
const { fleet_tab, upcoming_tab, recent_tab, strip, status, tabs, isk, elapsed, until, fit_label } = require('../src/renderer/fleet_view')

const FLEET = {
    id: 7, title: 'Hurricane Fleet', type_label: 'Strategic', live: true, started_at: '2026-10-16T19:00:00Z', start_time: '2026-10-16T19:30:00Z',
    fc_character_id: 5000, fc_name: 'The FC', fc_system_id: 1, fc_system_name: 'Huola',
    location_name: 'Amamake - Freeport', location_system_id: 30002537, location_system_name: 'Amamake', doctrine_name: 'Hurricane Fleet',
}

// One fleet as fleet_window.js view_of() hands it to the renderer.
function fleet_view_of(overrides = {}) {
    return {
        mode: 'fc', jumps: null, signed_up_key: null, loss: null, after_action: null, prepinged: false, reminder: false, feed: [],
        fleet: FLEET,
        counts: { in_fleet: 24, with_fc: 19, kills: 6, losses: 2, isk_destroyed: 1_420_000_000, isk_lost: 312_000_000 },
        ships: [
            { key: 'f:1', ship_type_id: 33157, ship_name: 'Hurricane Fleet Issue', role: 'primary', role_label: 'Mainline', flying: 14, signed_up: 15 },
            { key: 'f:2', ship_type_id: 11978, ship_name: 'Scimitar', role: 'support', role_label: 'Logi', flying: 2, signed_up: 2 },
        ],
        roles: [{ role: 'logi', covered: true }, { role: 'cyno', covered: false }],
        needs: [{ kind: 'ship', count: 1, label: 'Hurricane Fleet Issue', ship_type_id: 33157 }, { kind: 'role', count: 1, label: 'cyno' }],
        attention: [{ reason: 'capsule', names: ['Isa Varn'] }, { reason: 'off_doctrine', names: ['Rurik <b>Vance</b>', 'Oskel Dray'] }, { reason: 'not_in_fleet', names: ['Coro Vash'] }],
        pilots: [
            { character_id: 1, character_name: 'Ardo', ship_type_id: 33157, ship_name: 'Hurricane Fleet Issue', solar_system_id: 1, solar_system_name: 'Huola', docked: false, doctrine: true, capsule: false },
            { character_id: 2, character_name: 'Isa Varn', ship_type_id: 670, ship_name: 'Capsule', solar_system_id: 2, solar_system_name: 'Eszur', docked: false, doctrine: false, capsule: true },
        ],
        you: null,
        ...overrides,
    }
}

function snapshot({ kind = 'current', fleet = fleet_view_of(), ...rest } = {}) {
    return {
        loaded: true, error: null, notice: null, busy: null, synced_at: '2026-10-16T20:11:00Z',
        focus: { kind, id: fleet ? fleet.fleet.id : null, fleet },
        next: null, live: null, opened: null, recent: null, signups: {}, reminders: [],
        ...rest,
    }
}

const LIST = [
    { id: 7, type: 'strategic', type_label: 'Strategic', location: 'Huola', start_time: '2026-10-16T19:30:00Z', status: 'pending', live: true, doctrine: 'Hurricane Fleet', fc_character_id: 5000, fc_name: 'The FC' },
    { id: 8, type: 'training', type_label: 'Training', location: 'Amamake', start_time: '2099-10-18T19:00:00Z', status: 'pending', live: false, doctrine: null, fc_character_id: 5001, fc_name: 'Vel <i>Tamarin</i>' },
]
const KESRA = { character_id: 1001, character_name: 'Kesra Lund', ship_type_id: 587, ship_name: 'Rifter', solar_system_id: 2, solar_system_name: 'Eszur', doctrine: false, capsule: false }
const LOSS = { killmail_id: 77, killmail_time: '2026-10-16T20:01:00Z', ship_type_id: 33157, ship_name: 'Hurricane Fleet Issue', isk_value: 168e6, solar_system_name: 'Huola', srp_filed: false }

const all_html = parts => Object.values(parts).filter(v => typeof v === 'string').join('')

test('FC overview: three numbers, sub-view chips, short ships in amber, role gaps, attention grouped and escaped', () => {
    const parts = fleet_tab(snapshot(), { fc_view: 'overview' })
    assert.match(parts.main, /fw-stat">24</)
    assert.match(parts.main, /data-view="overview" aria-selected="true">Overview/)
    assert.match(parts.main, /fw-count fw-warn">14/)
    assert.match(parts.main, /No cyno/)
    assert.match(parts.main, /4 pilots/)
    assert.match(parts.main, /Signed up, not in fleet/)
    assert.match(parts.main, /Rurik &lt;b&gt;Vance&lt;\/b&gt;/)
    assert.match(parts.actions, /fleet:refresh-motd/)
    assert.equal(parts.site_id, 7)
})

test('FC pilots and kills sub-views', () => {
    const pilots = fleet_tab(snapshot(), { fc_view: 'pilots' })
    assert.match(pilots.main, /Huola · with you/)
    assert.match(pilots.main, /in pod/)
    assert.match(pilots.main, /characters\/2\/portrait/)

    const feed = [
        { killmail_id: 1, killmail_time: '2026-10-16T20:10:00Z', outcome: 'kill', ship_type_id: 24696, ship_name: 'Harbinger', victim_name: 'Seren', isk_value: 96e6, solar_system_name: 'Huola', fleet_pilots: 9, capsule: false },
        { killmail_id: 2, killmail_time: '2026-10-16T20:09:00Z', outcome: 'loss', ship_type_id: 33157, ship_name: 'Hurricane Fleet Issue', victim_name: 'Kesra Lund', isk_value: 168e6, solar_system_name: 'Huola', fleet_pilots: 0, capsule: false },
    ]
    const kills = fleet_tab(snapshot({ fleet: fleet_view_of({ feed }) }), { fc_view: 'kills' })
    assert.match(kills.main, /1\.42B/)
    assert.match(kills.main, /9 pilots on it/)
    assert.match(kills.main, /fw-kill fw-kill--loss/)
    assert.match(kills.main, /Kesra Lund · Huola/)
})

test('FC at minimum size gets the glance strip with bar widths as data, not styles', () => {
    const parts = fleet_tab(snapshot(), { compact: true })
    assert.match(parts.main, /data-pct="93"/)
    assert.match(parts.main, /4 pilots need attention/)
})

test('a member sees their ship and where they are, never other pilots', () => {
    const parts = fleet_tab(snapshot({ fleet: fleet_view_of({ mode: 'member', you: KESRA, jumps: 3, pilots: [], attention: [] }) }))
    assert.match(parts.main, /characters\/5000\/portrait/)          // the FC's portrait leads
    assert.match(parts.main, /Not a doctrine ship/)
    assert.match(parts.main, /3 jumps behind · fleet is in Huola/)
    assert.match(parts.main, /data-fleet-command="fleet:destination" data-id="1"/)
    assert.match(parts.main, /data-fleet-command="fleet:copy-fit" data-id="7" data-key="f:2"/)
    assert.doesNotMatch(parts.main, /Isa Varn|Ardo/)
})

test('a lost ship is a card above the fleet, with File SRP, Reship and a close that keeps SRP in Recent', () => {
    const v = fleet_view_of({ mode: 'member', you: { ...KESRA, ship_type_id: 670, ship_name: 'Capsule', capsule: true }, loss: LOSS })
    const parts = fleet_tab(snapshot({ fleet: v }))
    assert.match(parts.main, /Ship lost · 20:01 EVE/)
    assert.match(parts.main, /data-fleet-command="fleet:srp" data-id="77"/)
    assert.match(parts.main, /Reship in Amamake/)
    assert.match(parts.main, /data-fleet-command="fleet:dismiss-loss" data-id="77" aria-label="Close. SRP stays in Recent"/)
    // The fleet is still right there under the card.
    assert.match(parts.main, /In a pod · reship, then come back/)
    assert.match(parts.main, /Doctrine fits/)
    assert.match(fleet_tab(snapshot({ fleet: { ...v, loss: { ...LOSS, srp_filed: true } } })).main, /SRP filed ✓/)
})

test('a lost ship SRP does not cover has no File SRP', () => {
    const v = fleet_view_of({ mode: 'member', you: KESRA, loss: { ...LOSS, srp_covered: false } })
    const main = fleet_tab(snapshot({ fleet: v })).main
    assert.doesNotMatch(main, /fleet:srp/)
    assert.match(main, /not covered by SRP/)
    assert.match(main, /Reship in Amamake/)
})

test('wrap-up: ISK, what is left, Done, and the next fleet below', () => {
    const v = fleet_view_of({ fleet: { ...FLEET, live: false, ended_at: '2026-10-16T21:48:00Z' }, after_action: { pilots: 38, duration_seconds: 7560, losses: 4, srp_filed: 3, aar_link: null } })
    const parts = fleet_tab(snapshot({ kind: 'wrapup', fleet: v, next: LIST[1] }))
    assert.match(parts.main, /Fleet ended · 21:48 EVE/)
    assert.match(parts.main, /2h 06m · 38 pilots/)
    assert.match(parts.main, /3 of 4 losses filed/)
    assert.match(parts.main, /Link the AAR/)
    assert.match(parts.main, /fleet:done/)
    assert.match(parts.main, /Your next fleet/)
})

test('form-up for a sign-up that formed without you: three steps', () => {
    const v = fleet_view_of({ mode: 'viewer', jumps: 6, signed_up_key: 'f:1', you: null })
    const parts = fleet_tab(snapshot({ kind: 'formup', fleet: v }))
    assert.match(parts.main, /You're not in the fleet yet/)
    assert.match(parts.main, /Get to Huola/)
    assert.match(parts.main, /6 jumps<\/span> from you/)
    assert.match(parts.main, /Board a Hurricane Fleet Issue/)
    assert.match(parts.main, /X up for an invite/)
})

test('an FC on an alt: the header names the main as the alt, and pilots x up to the alt', () => {
    const fleet = { ...FLEET, fc_alt_character_id: 94234543, fc_alt_name: 'Henri Gray' }
    const v = fleet_view_of({ mode: 'viewer', jumps: 6, signed_up_key: 'f:1', you: null, fleet })
    const parts = fleet_tab(snapshot({ kind: 'formup', fleet: v }))
    assert.match(parts.main, /FC The FC as Henri Gray/)
    assert.match(parts.main, /Fleet chat in game · FC Henri Gray/)
})

test('FC pre-flight: checklist, sign-ups, pre-ping and Start', () => {
    const v = fleet_view_of({ fleet: { ...FLEET, live: false, start_time: '2099-01-01T18:00:00Z' } })
    const parts = fleet_tab(snapshot({ kind: 'prep', fleet: v }))
    assert.match(parts.main, /Ready to start/)
    assert.match(parts.main, /2 of 3/)
    assert.match(parts.main, /data-fleet-command="fleet:preping" data-id="7"/)
    assert.match(parts.main, /17 pilots/)
    assert.match(parts.actions, /data-fleet-command="fleet:start" data-id="7"/)
})

test('not in a fleet: the next fleet card leads with the FC portrait, EVE and local time and a ticking clock', () => {
    const parts = fleet_tab(snapshot({ kind: 'next', fleet: null, next: LIST[1], signups: { 8: { fit_name: '[FL33T] Rifter' } } }))
    assert.match(parts.main, /You're not in a fleet/)
    assert.match(parts.main, /Your next fleet/)
    assert.match(parts.main, /characters\/5001\/portrait/)
    assert.match(parts.main, /19:00 EVE <span class="fw-local h-[a-z]+" title="(Day|Night|Sleep)time">\d\d:\d\d local/)
    assert.match(parts.main, /data-clock="2099-10-18T19:00:00Z">\d+d \d\d:\d\d:\d\d</)
    assert.match(parts.main, /Signed up as Rifter/)
    assert.match(parts.main, /Vel &lt;i&gt;Tamarin&lt;\/i&gt;/)
})

// The v0.9.1 bug: list rows rendered empty, so there was nothing to click.
test('the schedule draws a row for every fleet, with your state on it', () => {
    const s = snapshot({ live: { id: 7, title: 'Hurricane Fleet', started_at: FLEET.started_at, mode: 'member', you: KESRA, jumps: 3 }, signups: { 8: { fit_name: 'Rifter' } } })
    const parts = upcoming_tab(s, LIST)
    assert.equal((parts.main.match(/class="fw-list-row/g) || []).length, 2)
    assert.match(parts.main, /data-open="7"/)
    assert.match(parts.main, /you are in/)
    assert.match(parts.main, /signed up/)
    assert.match(parts.main, /Training fleet/)
})

test('a tribe group fleet leads its FC with an outlined group chip; alliance fleets have none', () => {
    const group_row = { ...LIST[1], host_group: { id: 1, name: 'Dreads <b>' } }
    const parts = upcoming_tab(snapshot(), [LIST[0], group_row])
    assert.equal((parts.main.match(/class="fw-group-chip"/g) || []).length, 1)
    assert.match(parts.main, /<span class="fw-group-chip">Dreads &lt;b&gt;<\/span> FC Vel/)
    assert.doesNotMatch(upcoming_tab(snapshot(), LIST).main, /fw-group-chip/)

    const next = fleet_tab(snapshot({ kind: 'next', fleet: null, next: group_row })).main
    assert.match(next, /<span class="fw-group-chip">Dreads &lt;b&gt;<\/span> FC Vel/)
})

test('an opened fleet has a breadcrumb back, the ship picker and the reminder switch', () => {
    const v = fleet_view_of({ mode: 'viewer', fleet: { ...FLEET, id: 8, live: false, start_time: '2099-10-18T19:00:00Z' }, jumps: 5, signed_up_key: 'f:2', reminder: true })
    const parts = upcoming_tab(snapshot({ opened: { id: 8, is_current: false, row: LIST[1], fleet: v } }), LIST)
    assert.match(parts.main, /data-close aria-label="Back to upcoming fleets"/)
    assert.match(parts.main, /Form up in Amamake - Freeport/)
    assert.match(parts.main, / · 5 jumps from you/)
    assert.match(parts.main, /aria-checked="true" data-interactive data-fleet-command="fleet:sign-up" data-id="8" data-key="f:2"/)
    assert.match(parts.main, /Signed up as Scimitar/)
    assert.match(parts.main, /role="switch" aria-checked="true"[^>]*data-fleet-command="fleet:remind" data-id="8"/)
    assert.equal(parts.site_id, 8)
})

test('Recent: SRP still owed first, then your last fleets with their SRP state', () => {
    const recent = {
        srp_owed: 1,
        fleets: [
            { fleet_id: 7, title: 'Hurricane Fleet', started_at: '2026-10-16T19:00:00Z', ended_at: '2026-10-16T21:05:00Z', live: false, was_fc: false, kills: 6, losses: 2,
              my_losses: [{ killmail_id: 77, ship_type_id: 33157, ship_name: 'Hurricane Fleet Issue', isk_value: 168e6, solar_system_name: 'Huola', killmail_time: '2026-10-16T20:01:00Z', srp_status: 'none', srp_amount: 0 }] },
            { fleet_id: 5, title: 'Structure defence', started_at: '2026-10-13T19:00:00Z', ended_at: '2026-10-13T21:05:00Z', live: false, was_fc: true, kills: 1, losses: 1,
              my_losses: [{ killmail_id: 70, ship_type_id: 587, ship_name: 'Rifter', isk_value: 2e6, solar_system_name: 'Amamake', killmail_time: '2026-10-13T20:01:00Z', srp_status: 'approved', srp_amount: 42e6 }] },
        ],
    }
    const parts = recent_tab(snapshot({ recent }))
    assert.match(parts.main, /SRP to file/)
    assert.match(parts.main, /data-fleet-command="fleet:srp" data-id="77"/)
    assert.match(parts.main, /SRP not filed/)
    assert.match(parts.main, /SRP paid 42M/)
    assert.match(parts.main, /you were FC/)
    assert.match(parts.main, /2h 05m/)
    assert.doesNotMatch(recent_tab(snapshot({ recent: { srp_owed: 0, fleets: [] } })).main, /SRP to file/)
})

test('Recent: fleets are schedule-style rows grouped by day, with the FC, the fleet type and the ISK bar', () => {
    const lost = { ship_type_id: 11198, ship_name: 'Stiletto', isk_value: 60e6, solar_system_name: 'Huola', killmail_time: '2026-10-16T20:01:00Z', srp_status: 'none', srp_amount: 0, srp_covered: false }
    const recent = {
        srp_owed: 0,
        fleets: [
            { fleet_id: 9, title: 'TFIs', type: 'strategic', type_label: 'Strategic', fc_character_id: 2112, fc_name: 'Arifsdald', started_at: '2026-10-16T19:00:00Z', ended_at: '2026-10-16T21:26:00Z', live: false, was_fc: false,
              kills: 72, losses: 84, isk_destroyed: 9e9, isk_lost: 3e9, my_losses: [{ ...lost, killmail_id: 1 }, { ...lost, killmail_id: 2 }] },
            { fleet_id: 8, title: 'Plexing', type_label: 'Non-Strategic', started_at: '2026-10-15T19:00:00Z', ended_at: '2026-10-15T20:45:00Z', live: false, was_fc: true,
              kills: 8, losses: 0, isk_destroyed: 0, isk_lost: 0, my_losses: [] },
        ],
    }
    const main = recent_tab(snapshot({ recent })).main
    assert.doesNotMatch(main, /Your last fleets/)
    assert.equal((main.match(/class="fw-section"/g) || []).length, 2)
    assert.match(main, /class="fw-list-row fw-recent"[^>]*data-id="9"/)
    assert.match(main, /fleet-type--strategic">Strategic/)
    assert.match(main, /19:00 EVE · 2h 26m · FC Arifsdald/)
    assert.match(main, /No SRP ×2/)
    assert.match(main, /class="fw-kill-text">72 kills/)
    assert.match(main, /class="fw-danger">84 lost/)
    assert.match(main, /aria-label="ISK efficiency 75 percent: 9\.00B destroyed, 3\.00B lost"><span data-pct="75">/)
    // An older backend sends no type or FC: no badge, a blank portrait, and no ISK bar for an empty fleet.
    assert.match(main, /Plexing<\/span>/)
    assert.match(main, /class="eve-dim">0 lost/)
    assert.equal((main.match(/fw-efficiency__bar/g) || []).length, 1)
})

test('Recent: a loss SRP does not cover is not owed and has no File SRP', () => {
    const recent = {
        srp_owed: 0,
        fleets: [{ fleet_id: 7, title: 'Roam', started_at: '2026-10-16T19:00:00Z', ended_at: '2026-10-16T21:05:00Z', live: false, was_fc: false, kills: 6, losses: 1,
            my_losses: [{ killmail_id: 77, ship_type_id: 11198, ship_name: 'Stiletto', isk_value: 60e6, solar_system_name: 'Huola', killmail_time: '2026-10-16T20:01:00Z', srp_status: 'none', srp_amount: 0, srp_covered: false }] }],
    }
    const main = recent_tab(snapshot({ recent })).main
    assert.doesNotMatch(main, /SRP to file/)
    assert.doesNotMatch(main, /fleet:srp/)
    assert.match(main, /class="fw-tag eve-dim" title="No SRP">No SRP</)
})

test('the return strip and the tab badges', () => {
    const live = { id: 7, title: 'Hurricane Fleet', started_at: FLEET.started_at, mode: 'member', you: { ...KESRA, capsule: true }, jumps: 3 }
    assert.match(strip(snapshot({ live })), /data-tab="fleet"[\s\S]*in a pod[\s\S]*Back to fleet/)
    assert.match(strip(snapshot({ live: { ...live, you: KESRA } })), /3 jumps behind/)
    assert.equal(strip(snapshot()), '')
    assert.deepEqual(tabs(snapshot({ live, recent: { srp_owed: 2, fleets: [] } }), LIST), { live: true, upcoming: 2, owed: true })
})

test('the status bar shows one message at a time', () => {
    assert.match(status(snapshot()), /Synced 20:11 EVE/)
    const notice = status(snapshot({ notice: 'Fit copied' }))
    assert.match(notice, /Fit copied/)
    assert.doesNotMatch(notice, /Synced/)
    assert.match(status(snapshot({ error: 'Could not reach Minmatar Fleet. Retrying…' })), /fw-status--error/)
})

test('no view ever writes an inline style (CSP is style-src self)', () => {
    const s = snapshot({ fleet: fleet_view_of({ loss: LOSS }) })
    const html = [
        all_html(fleet_tab(s, {})), all_html(fleet_tab(s, { fc_view: 'kills' })), all_html(fleet_tab(s, { compact: true })),
        all_html(upcoming_tab(s, LIST)), strip(snapshot({ live: { id: 7, title: 'x', started_at: FLEET.started_at, mode: 'fc' } })),
    ].join('')
    assert.doesNotMatch(html, /style=/)
})

// Two functions with one name in a classic script: the later silently replaces the earlier (v0.9.1).
test('the window scripts declare each top-level function once', () => {
    for (const file of ['fleets.js', 'fleet_view.js', 'fleet_format.js']) {
        const source = fs.readFileSync(path.join(__dirname, '..', 'src', 'renderer', file), 'utf8')
        const names = [...source.matchAll(/^(?: {4})?function (\w+)\(/gm)].map(m => m[1])
        assert.deepEqual(names.filter((n, i) => names.indexOf(n) !== i), [], file)
    }
})

test('formatting helpers', () => {
    assert.equal(isk(3_100_000_000), '3.10B')
    assert.equal(isk(640_000_000), '640M')
    assert.equal(isk(950_000), '950K')
    const now = new Date('2026-10-16T20:12:08Z')
    assert.equal(elapsed('2026-10-16T19:00:00Z', now), '1:12:08')
    assert.equal(until('2026-10-16T20:26:13Z', now), '14:05')
    assert.equal(fit_label('[FL33T] Hurricane Fleet Issue'), 'Hurricane Fleet Issue')
})
