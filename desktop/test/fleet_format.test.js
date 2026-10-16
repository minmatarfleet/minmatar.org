const { test } = require('node:test')
const assert = require('node:assert/strict')
const { eve_time, day_label, countdown, group_by_day } = require('../src/renderer/fleet_format')

const NOW = new Date('2026-10-16T17:30:00Z')

test('EVE time is UTC', () => {
    assert.equal(eve_time('2026-10-16T18:05:00Z'), '18:05')
})

test('day labels follow UTC days', () => {
    assert.equal(day_label('2026-10-16T23:59:00Z', NOW), 'Today')
    assert.equal(day_label('2026-10-17T00:01:00Z', NOW), 'Tomorrow')
    assert.equal(day_label('2026-10-19T12:00:00Z', NOW), 'Mon 19 Oct')
})

test('countdown', () => {
    assert.equal(countdown('2026-10-16T18:00:00Z', NOW), 'in 30m 00s')
    assert.equal(countdown('2026-10-16T20:15:00Z', NOW), 'in 2h 45m')
    assert.equal(countdown('2026-10-18T19:30:00Z', NOW), 'in 2d 2h')
    assert.equal(countdown('2026-10-16T17:00:00Z', NOW), 'started 30m 00s ago')
})

test('live fleets group first, then by day in order', () => {
    const groups = group_by_day([
        { id: 1, start_time: '2026-10-16T18:00:00Z' },
        { id: 2, start_time: '2026-10-17T18:00:00Z' },
        { id: 3, start_time: '2026-10-16T16:00:00Z', live: true },
    ], NOW)
    assert.deepEqual(groups.map(g => g.label), ['Live now', 'Today', 'Tomorrow'])
    assert.deepEqual(groups[0].fleets.map(f => f.id), [3])
})
