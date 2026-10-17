const { test } = require('node:test')
const assert = require('node:assert/strict')
const { change_tone, change_text, bar, activity_text, ago_text, flip_tone, row_title } = require('../src/renderer/campaign_format')

test('the move rounds to whole points and carries its sign', () => {
    assert.equal(change_text(8.04), '+8%')
    assert.equal(change_text(-3.2), '-3%')
    assert.equal(change_text(0.4), '0%')
    assert.equal(change_text(-0.4), '0%')
    assert.equal(change_text(null), '')
})

test('tone follows the rounded move; no reading is its own state', () => {
    assert.equal(change_tone(8), 'up')
    assert.equal(change_tone(-3), 'down')
    assert.equal(change_tone(0.4), 'steady')
    assert.equal(change_tone(null), 'none')
})

test('a gain is drawn from the week\'s start to now, a loss from now back to it', () => {
    assert.deepEqual(bar(62, 8), { fill: 54, delta_from: 54, delta_width: 8 })
    assert.deepEqual(bar(41, -6), { fill: 41, delta_from: 41, delta_width: 6 })
    assert.deepEqual(bar(91, null), { fill: 91, delta_from: 91, delta_width: 0 })
    assert.deepEqual(bar(null, null), { fill: 0, delta_from: 0, delta_width: 0 })
    assert.deepEqual(bar(3, 10), { fill: 0, delta_from: 0, delta_width: 3 })   // clamped at the empty end
})

test('a flip replaces the move: taken is good news, lost is bad', () => {
    assert.equal(flip_tone('captured'), 'up')
    assert.equal(flip_tone('lost'), 'down')
    assert.equal(flip_tone(null), null)
})

test('the hover carries the week\'s move and the day\'s beside it', () => {
    const system = { detail: '1,860 of 3,000 victory points', change: 22, change_period: 'week', change_24h: 8, flipped: null }
    assert.equal(row_title(system), '1,860 of 3,000 victory points · +22% this week · +8% in 24 hours')
    assert.equal(row_title({ ...system, flipped: 'captured', change: null }), '1,860 of 3,000 victory points · Captured this week · +8% in 24 hours')
    assert.equal(row_title({ ...system, change_24h: null }), '1,860 of 3,000 victory points · +22% this week')
    // A backend from before the weekly move: the day is the move, said once.
    assert.equal(row_title({ detail: '', change: 8, change_period: '24h', change_24h: 8 }), '+8% in 24 hours')
})

test('activity reads as a short sentence', () => {
    assert.equal(activity_text({ kills: 2, in_fleet: true }), '2 kills, in fleet')
    assert.equal(activity_text({ complexes: 1 }), 'Captured a complex')
    assert.equal(activity_text({ losses: 1, advantage_sites: 3 }), '1 loss, 3 advantage sites')
    assert.equal(activity_text({}), 'Active')
})

test('ago text', () => {
    const now = new Date('2026-10-16T18:00:00Z')
    assert.equal(ago_text('2026-10-16T17:57:10Z', now), '2 min ago')
    assert.equal(ago_text('2026-10-16T17:59:50Z', now), 'just now')
    assert.equal(ago_text('2026-10-16T16:46:00Z', now), '1h 14m ago')
})
