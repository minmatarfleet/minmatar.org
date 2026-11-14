import { describe, expect, it } from 'vitest'
import { angular_velocity, missile_applied_fraction, turret_applied_fraction, turret_damage_multiplier, turret_hit_chance } from '@helpers/sims/application'

const shot = { target_speed_ms: 0, transversal_fraction: 1, target_signature_m: 400, distance_m: 10000, tracking: 1, optimal_m: 20000, falloff_m: 10000 }

describe('turret application', () => {
    it('hits 100% on a still target in optimal', () => {
        expect(turret_hit_chance(shot)).toBe(1)
    })

    it('halves at optimal + falloff', () => {
        expect(turret_hit_chance({ ...shot, distance_m: 30000 })).toBeCloseTo(0.5, 12)
    })

    it('halves when the tracking term is 1', () => {
        // angular * 40000 / (tracking * sig) = 1  =>  angular = 0.01 rad/s
        expect(turret_hit_chance({ ...shot, target_speed_ms: 100, distance_m: 10000 })).toBeCloseTo(0.5, 12)
        expect(angular_velocity(100, 10000)).toBeCloseTo(0.01, 12)
    })

    it('combines tracking and range terms in one exponent', () => {
        expect(turret_hit_chance({ ...shot, target_speed_ms: 300, distance_m: 30000 })).toBeCloseTo(0.25, 12)
    })

    it('expected multiplier is 1.015 at a sure hit, 3x chance below 1%', () => {
        expect(turret_damage_multiplier(1)).toBeCloseTo(1.01505, 6)
        expect(turret_damage_multiplier(0.005)).toBeCloseTo(0.015, 12)
        expect(turret_damage_multiplier(0)).toBe(0)
        expect(turret_damage_multiplier(0.5)).toBeCloseTo((0.25 + 0.49 + 0.0501) / 2, 12)
        expect(turret_applied_fraction(shot)).toBe(1)
    })
})

describe('missile application', () => {
    const missile = { target_signature_m: 125, target_speed_ms: 230, explosion_radius_m: 330, explosion_velocity_ms: 69, drf: 0.882 }

    it('is 1 against a big slow target', () => {
        expect(missile_applied_fraction({ ...missile, target_signature_m: 400, target_speed_ms: 0 })).toBe(1)
    })

    it('is S/Er against a still small target', () => {
        expect(missile_applied_fraction({ ...missile, target_speed_ms: 0 })).toBeCloseTo(125 / 330, 12)
    })

    it('uses the speed term when it is the smallest', () => {
        const expected = ((125 / 330) * (69 / 230)) ** 0.882
        expect(missile_applied_fraction(missile)).toBeCloseTo(expected, 12)
    })
})
