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

test('the fleet clock ticks HH:MM:SS to the start, then counts up', () => {
    const { clock } = require('../src/renderer/fleet_format')
    assert.deepEqual(clock('2026-10-16T18:00:00Z', NOW), { text: '00:30:00', started: false })
    assert.deepEqual(clock('2026-10-18T19:30:05Z', NOW), { text: '2d 02:00:05', started: false })
    assert.deepEqual(clock('2026-10-16T17:00:00Z', NOW), { text: '+00:30:00', started: true })
})

test('local time carries the hour band and its word, like the site', () => {
    const { local_time } = require('../src/renderer/fleet_format')
    const at = hour => { const d = new Date(2026, 9, 16, hour, 5); return local_time(d.toISOString()) }
    assert.deepEqual(at(3), { text: '03:05', band: 'h-sleep', word: 'Sleeptime' })
    assert.deepEqual(at(12), { text: '12:05', band: 'h-day', word: 'Daytime' })
    assert.deepEqual(at(20), { text: '20:05', band: 'h-evening', word: 'Nighttime' })
    assert.deepEqual(at(23), { text: '23:05', band: 'h-midnight', word: 'Sleeptime' })
})
