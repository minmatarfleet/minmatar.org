import { describe, expect, it } from 'vitest'
import { bonused_strengths, combined_jam_chance, ECM_RULES, expected_jammed, jam_chance, sensor_of, strongest_sensor } from '@helpers/sims/ecm'

const ladar = { radar: 1.3, ladar: 4, magnetometric: 1.3, gravimetric: 1.3 }
const multi = { radar: 2.6, ladar: 2.6, magnetometric: 2.6, gravimetric: 2.6 }

describe('ecm', () => {
    it('uses the strength for the target sensor type', () => {
        expect(jam_chance(ladar, { sensor_type: 'ladar', sensor_strength: 16 })).toBeCloseTo(0.25, 12)
        expect(jam_chance(ladar, { sensor_type: 'radar', sensor_strength: 13 })).toBeCloseTo(0.1, 12)
        expect(jam_chance(multi, { sensor_type: 'radar', sensor_strength: 13 })).toBeCloseTo(0.2, 12)
    })

    it('caps the chance at 1', () => {
        expect(jam_chance(ladar, { sensor_type: 'ladar', sensor_strength: 2 })).toBe(1)
        expect(combined_jam_chance([1, 0.5])).toBe(1)
    })

    it('applies hull bonuses per level', () => {
        expect(bonused_strengths(ladar, 20, 5).ladar).toBeCloseTo(8, 12)
        expect(bonused_strengths(ladar, 15, 5).ladar).toBeCloseTo(7, 12)
    })

    it('spreading jammers beats stacking them', () => {
        const p = 0.47
        const spread = expected_jammed([[p, p], [p, p], [p, p]])
        const stacked = expected_jammed([[p, p, p, p, p, p], [], []])
        expect(spread).toBeGreaterThan(2)
        expect(stacked).toBeLessThan(1)
        expect(combined_jam_chance([0.5, 0.5])).toBeCloseTo(0.75, 12)
    })

    it('finds a racial jammer and a hull sensor type', () => {
        expect(strongest_sensor(ladar)).toBe('ladar')
        expect(sensor_of({ radar: 19, ladar: 0, magnetometric: 0, gravimetric: 0 })).toEqual({ sensor_type: 'radar', sensor_strength: 19 })
    })

    it('records the post-2018 rule that a jammed ship can lock its jammer', () => {
        expect(ECM_RULES.jammed_ship_can_lock_jammer).toBe(true)
    })
})
