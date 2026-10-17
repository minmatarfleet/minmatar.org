import { describe, expect, test } from 'vitest'
import { fleet_phase, type FleetPhaseFields } from '@helpers/fleet_phase'

const START = new Date('2026-10-01T18:00:00Z')
const END = new Date('2026-10-01T20:00:00Z')
const tracking = (end_time: Date | null) => ({ id: 1, start_time: START, end_time, is_registered: true })

// The branches FleetFeedItem, FleetListItem and FleetStatus used before fleet_phase existed.
function legacy_phase(fleet: FleetPhaseFields) {
    if (fleet?.status === 'cancelled') return 'cancelled'
    if (fleet?.status !== 'cancelled' && fleet?.tracking && !fleet?.tracking?.end_time) return 'active'
    if (fleet?.status !== 'cancelled' && fleet?.tracking && fleet?.tracking?.end_time) return 'completed'
    return 'upcoming'
}

const CASES: [string, FleetPhaseFields, string][] = [
    ['scheduled, never started', { status: 'active' }, 'upcoming'],
    ['no status, never started', {}, 'upcoming'],
    ['null tracking', { status: 'active', tracking: null }, 'upcoming'],
    ['tracking without end', { status: 'active', tracking: tracking(null) }, 'active'],
    ['tracking with end', { status: 'complete', tracking: tracking(END) }, 'completed'],
    ['end time as an API string', { tracking: { end_time: '2026-10-01T20:00:00Z' } }, 'completed'],
    ['cancelled before start', { status: 'cancelled' }, 'cancelled'],
    ['cancelled while tracking', { status: 'cancelled', tracking: tracking(null) }, 'cancelled'],
    ['cancelled after it ended', { status: 'cancelled', tracking: tracking(END) }, 'cancelled'],
]

describe('fleet_phase', () => {
    test.each(CASES)('%s', (_name, fleet, expected) => {
        expect(fleet_phase(fleet)).toBe(expected)
    })

    test.each(CASES)('matches the old component branches: %s', (_name, fleet) => {
        expect(fleet_phase(fleet)).toBe(legacy_phase(fleet))
    })
})
