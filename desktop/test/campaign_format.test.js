const { test } = require('node:test')
const assert = require('node:assert/strict')
const { change_tone, change_text, bar, activity_text, ago_text } = require('../src/renderer/campaign_format')

test('the 24h move rounds to whole points and carries its sign', () => {
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

test('a gain is drawn from yesterday to now, a loss from now to yesterday', () => {
    assert.deepEqual(bar(62, 8), { fill: 54, delta_from: 54, delta_width: 8 })
    assert.deepEqual(bar(41, -6), { fill: 41, delta_from: 41, delta_width: 6 })
    assert.deepEqual(bar(91, null), { fill: 91, delta_from: 91, delta_width: 0 })
    assert.deepEqual(bar(null, null), { fill: 0, delta_from: 0, delta_width: 0 })
    assert.deepEqual(bar(3, 10), { fill: 0, delta_from: 0, delta_width: 3 })   // clamped at the empty end
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
