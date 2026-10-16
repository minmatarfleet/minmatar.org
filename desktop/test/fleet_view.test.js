const { test } = require('node:test')
const assert = require('node:assert/strict')
const { render, isk, elapsed, until } = require('../src/renderer/fleet_view')

function snapshot(overrides = {}) {
    return {
        view: 'fleet', mode: 'fc', opened: false, jumps: null, notice: null, busy: null, error: null, signed_up_key: null, loss: null, after_action: null,
        fleet: {
            id: 7, title: 'Hurricane Fleet', type_label: 'Strategic', live: true, started_at: '2026-10-16T19:00:00Z', start_time: '2026-10-16T19:30:00Z',
            fc_character_id: 5000, fc_name: 'The FC', fc_system_id: 1, fc_system_name: 'Huola', location_name: 'Amamake - Freeport', location_system_name: 'Amamake',
        },
        counts: { in_fleet: 24, with_fc: 19, kills: 6, losses: 2, isk_destroyed: 1_420_000_000, isk_lost: 312_000_000 },
        ships: [
            { key: 'f:1', ship_type_id: 33157, ship_name: 'Hurricane Fleet Issue', role: 'primary', flying: 14, signed_up: 15 },
            { key: 'f:2', ship_type_id: 11978, ship_name: 'Scimitar', role: 'support', flying: 2, signed_up: 2 },
        ],
        roles: [{ role: 'logi', covered: true }, { role: 'cyno', covered: false }],
        needs: [{ kind: 'ship', count: 1, label: 'Hurricane Fleet Issue', ship_type_id: 33157 }, { kind: 'role', count: 1, label: 'cyno' }],
        attention: [{ reason: 'capsule', names: ['Isa Varn'] }, { reason: 'off_doctrine', names: ['Rurik <b>Vance</b>', 'Oskel Dray'] }],
        pilots: [
            { character_id: 1, character_name: 'Ardo', ship_type_id: 33157, ship_name: 'Hurricane Fleet Issue', solar_system_id: 1, solar_system_name: 'Huola', docked: false, doctrine: true, capsule: false },
            { character_id: 2, character_name: 'Isa Varn', ship_type_id: 670, ship_name: 'Capsule', solar_system_id: 2, solar_system_name: 'Eszur', docked: false, doctrine: false, capsule: true },
        ],
        you: null,
        ...overrides,
    }
}

test('FC summary: three numbers, short ships in amber, role gaps, attention grouped and escaped', () => {
    const parts = render(snapshot(), { tab: 'summary' })
    assert.match(parts.top, /fw-stat">24</)
    assert.match(parts.top, /aria-selected="true">Summary/)
    assert.match(parts.main, /fw-count fw-warn">14/)          // 14 of 15
    assert.match(parts.main, /fw-count">2</)                  // full
    assert.match(parts.main, /No cyno/)
    assert.match(parts.main, /3 pilots/)
    assert.match(parts.main, /Rurik &lt;b&gt;Vance&lt;\/b&gt;/)
    assert.match(parts.main, /images\.evetech\.net\/types\/33157\/icon\?size=64/)
    assert.match(parts.foot, /fleet:refresh-motd/)
    assert.doesNotMatch(parts.main + parts.top, /style=/)    // CSP: no inline styles
})

test('FC pilots tab groups the roster by system', () => {
    const parts = render(snapshot(), { tab: 'pilots' })
    assert.match(parts.main, /Huola · with you/)
    assert.match(parts.main, /Eszur/)
    assert.match(parts.main, /in pod/)
    assert.match(parts.main, /characters\/2\/portrait/)
})

test('FC at minimum size gets the glance strip with bar widths as data, not styles', () => {
    const parts = render(snapshot(), { compact: true })
    assert.equal(parts.top, '')
    assert.match(parts.main, /data-pct="93"/)
    assert.match(parts.main, /3 pilots need attention/)
    assert.doesNotMatch(parts.main, /style=/)
})

test('a member never sees names of other pilots', () => {
    const you = { character_id: 1001, character_name: 'Kesra Lund', ship_type_id: 587, ship_name: 'Rifter', solar_system_id: 2, solar_system_name: 'Eszur', doctrine: false, capsule: false }
    const parts = render(snapshot({ mode: 'member', you, jumps: 3, pilots: [], attention: [] }))
    assert.match(parts.main, /Not a doctrine ship/)
    assert.match(parts.main, /3 jumps behind · fleet is in Huola/)
    assert.match(parts.main, /1 Hurricane Fleet Issue/)
    assert.match(parts.main, /1 cyno/)
    assert.match(parts.main, /fleet:copy-fit" data-key="f:2"/)
    assert.doesNotMatch(parts.main + parts.top, /Isa Varn|Ardo/)
})

test('form-up: countdown, form-up place with jumps, ship picker with the pilot\'s sign-up checked', () => {
    const parts = render(snapshot({ mode: 'viewer', fleet: { ...snapshot().fleet, live: false }, jumps: 5, signed_up_key: 'f:2' }))
    assert.equal(parts.title, 'Form-up')
    assert.match(parts.top, /data-start="2026-10-16T19:30:00Z"/)
    assert.match(parts.main, /Form up in Amamake - Freeport · 5 jumps/)
    assert.match(parts.main, /aria-checked="true" data-interactive data-fleet-command="fleet:sign-up" data-key="f:2"/)
    assert.match(parts.main, /Signed up as Scimitar/)
})

test('ship lost and after-action', () => {
    const loss = { killmail_id: 77, killmail_time: '2026-10-16T20:01:00Z', ship_type_id: 33157, ship_name: 'Hurricane Fleet Issue', isk_value: 168e6, solar_system_name: 'Huola', srp_filed: false }
    const lost = render(snapshot({ view: 'loss', mode: 'member', loss }))
    assert.match(lost.top, /Ship lost/)
    assert.match(lost.top, /168M ISK · 20:01 EVE/)
    assert.match(lost.main, /fleet:srp/)
    assert.match(render(snapshot({ view: 'loss', loss: { ...loss, srp_filed: true } })).main, /SRP filed/)

    const after = render(snapshot({ view: 'after', fleet: { ...snapshot().fleet, live: false, ended_at: '2026-10-16T21:48:00Z' }, after_action: { pilots: 38, duration_seconds: 7560, losses: 4, srp_filed: 3, aar_link: null } }))
    assert.match(after.top, /Ended 21:48 EVE · 2h 06m · 38 pilots/)
    assert.match(after.main, /1\.42B/)
    assert.match(after.main, /3 of 4 losses filed/)
    assert.match(after.main, /Link the AAR/)
    assert.match(after.foot, /fleet:done/)
})

test('formatting helpers', () => {
    assert.equal(isk(3_100_000_000), '3.10B')
    assert.equal(isk(640_000_000), '640M')
    assert.equal(isk(950_000), '950K')
    const now = new Date('2026-10-16T20:12:08Z')
    assert.equal(elapsed('2026-10-16T19:00:00Z', now), '1:12:08')
    assert.equal(until('2026-10-16T20:26:13Z', now), '14:05')
})
