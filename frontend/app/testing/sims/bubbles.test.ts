import { describe, expect, it } from 'vitest'
import { GATE_JUMP_RANGE_M, is_held, segment_entry, warp_landing } from '@helpers/sims/bubbles'

const gate = { x: 0, y: 0 }
const sun = { x: -1e9, y: 0 }

describe('warp_landing', () => {
    it('lands on the destination when no bubble is in the way', () => {
        const landing = warp_landing(sun, gate, [])
        expect(landing.caught).toBe(false)
        expect(landing.distance_to_destination).toBe(0)
        expect(landing.in_jump_range).toBe(true)
    })

    it('drops out at the near edge of a bubble on the warp line', () => {
        const landing = warp_landing(sun, gate, [{ center: { x: -50000, y: 0 }, radius: 20000 }])
        expect(landing.caught).toBe(true)
        expect(landing.landing.x).toBeCloseTo(-70000, 0)
        expect(landing.distance_to_destination).toBeCloseTo(70000, 0)
        expect(landing.burn_to_jump_range).toBeCloseTo(70000 - GATE_JUMP_RANGE_M, 0)
        expect(is_held(landing)).toBe(true)
    })

    it('uses the first bubble along the path', () => {
        const landing = warp_landing(sun, gate, [
            { center: { x: -20000, y: 0 }, radius: 5000 },
            { center: { x: -60000, y: 0 }, radius: 5000 },
        ])
        expect(landing.bubble_index).toBe(1)
        expect(landing.distance_to_destination).toBeCloseTo(65000, 0)
    })

    it('misses a bubble off the line and one behind the destination', () => {
        expect(warp_landing(sun, gate, [{ center: { x: -50000, y: 25000 }, radius: 20000 }]).caught).toBe(false)
        expect(warp_landing(sun, gate, [{ center: { x: 30000, y: 0 }, radius: 20000 }]).caught).toBe(false)
    })

    it('a bubble on the gate catches at its edge, a grazing one inside jump range does not hold', () => {
        const on_gate = warp_landing(sun, gate, [{ center: gate, radius: 20000 }])
        expect(on_gate.distance_to_destination).toBeCloseTo(20000, 0)
        const grazing = warp_landing(sun, gate, [{ center: { x: 18500, y: 0 }, radius: 20000 }])
        expect(grazing.caught).toBe(true)
        expect(grazing.in_jump_range).toBe(true)
        expect(is_held(grazing)).toBe(false)
    })

    it('segment_entry reports a start inside the sphere as t = 0', () => {
        expect(segment_entry({ x: 0, y: 0 }, { x: 100, y: 0 }, { center: { x: 0, y: 0 }, radius: 10 })).toBe(0)
    })
})
