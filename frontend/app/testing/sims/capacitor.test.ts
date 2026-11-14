import { describe, expect, it } from 'vitest'
import { cap_recharge_rate, falloff_effectiveness, peak_recharge_rate, simulate_cap_pressure, stable_level, step_capacitor } from '@helpers/sims/capacitor'

describe('capacitor recharge', () => {
    it('peaks at 25% with 2.5 * Cmax / tau', () => {
        const cap_max = 2250
        const tau = 500
        const rates = Array.from({ length: 101 }, (_, i) => cap_recharge_rate((i / 100) * cap_max, cap_max, tau))
        expect(rates.indexOf(Math.max(...rates))).toBe(25)
        expect(cap_recharge_rate(0.25 * cap_max, cap_max, tau)).toBeCloseTo(peak_recharge_rate(cap_max, tau), 9)
        expect(peak_recharge_rate(cap_max, tau)).toBeCloseTo(11.25, 9)
        expect(cap_recharge_rate(0, cap_max, tau)).toBe(0)
        expect(cap_recharge_rate(cap_max, cap_max, tau)).toBe(0)
    })

    it('steps with the closed form, recovering even from empty', () => {
        expect(step_capacitor(0, 1000, 100, 0)).toBe(0)
        expect(step_capacitor(0, 1000, 100, 10)).toBeGreaterThan(0)
        // tau is roughly the time to go from empty to ~98.7%: (1 - e^-5)^2
        expect(step_capacitor(0, 1000, 100, 100) / 1000).toBeCloseTo((1 - Math.exp(-5)) ** 2, 9)
        // Matches the differential form over a small step
        const c = 400
        expect((step_capacitor(c, 1000, 100, 0.001) - c) / 0.001).toBeCloseTo(cap_recharge_rate(c, 1000, 100), 2)
    })

    it('stable_level matches the drain and fails above the peak', () => {
        const level = stable_level(5, 2250, 500) as number
        expect(cap_recharge_rate(level * 2250, 2250, 500)).toBeCloseTo(5, 9)
        expect(level).toBeGreaterThan(0.25)
        expect(stable_level(11.25, 2250, 500)).toBeCloseTo(0.25, 9)
        expect(stable_level(11.3, 2250, 500)).toBeNull()
    })
})

describe('falloff_effectiveness', () => {
    it('is 1 inside optimal, 0.5 at optimal + falloff, 1/16 at two falloffs', () => {
        expect(falloff_effectiveness(20000, 20000, 10000)).toBe(1)
        expect(falloff_effectiveness(30000, 20000, 10000)).toBeCloseTo(0.5, 12)
        expect(falloff_effectiveness(40000, 20000, 10000)).toBeCloseTo(0.0625, 12)
    })
})

describe('simulate_cap_pressure', () => {
    const neut = { amount: 600, cycle_s: 24, optimal_m: 20000, falloff_m: 10000 }

    it('a heavy neut drains 600 GJ at the start of the cycle', () => {
        const r = simulate_cap_pressure({ cap_max: 2250, recharge_s: 500, duration_s: 1, dt_s: 0.5, neuts: [{ ...neut, count: 1 }] })
        expect(r.series[0].cap).toBe(2250)
        expect(r.series[1].cap).toBeLessThan(1700)
        expect(r.empty_at).toBeNull()
    })

    it('enough neuts empty the capacitor and shut off a module', () => {
        const r = simulate_cap_pressure({ cap_max: 2250, recharge_s: 500, duration_s: 60, neuts: [{ ...neut, count: 4 }], modules: [{ amount: 90, cycle_s: 6, count: 1 }] })
        expect(r.empty_at).toBe(0)
        expect(r.module_off_at).toBe(0)
        expect(r.failed_cycles).toBeGreaterThan(0)
    })

    it('range weakens neuts and transfers hold the capacitor up', () => {
        const near = simulate_cap_pressure({ cap_max: 2250, recharge_s: 500, duration_s: 60, range_m: 15000, neuts: [{ ...neut, count: 2 }] })
        const far = simulate_cap_pressure({ cap_max: 2250, recharge_s: 500, duration_s: 60, range_m: 35000, neuts: [{ ...neut, count: 2 }] })
        expect(far.lowest_fraction).toBeGreaterThan(near.lowest_fraction)
        const fed = simulate_cap_pressure({ cap_max: 2250, recharge_s: 500, duration_s: 60, range_m: 15000, neuts: [{ ...neut, count: 2 }], transfers: [{ amount: 351, cycle_s: 5, count: 1 }] })
        expect(fed.lowest_fraction).toBeGreaterThan(near.lowest_fraction)
    })

    it('a steady drain above the peak empties it', () => {
        const r = simulate_cap_pressure({ cap_max: 2250, recharge_s: 500, duration_s: 900, dt_s: 1, drain_gj_per_s: 13 })
        expect(r.empty_at).not.toBeNull()
        const held = simulate_cap_pressure({ cap_max: 2250, recharge_s: 500, duration_s: 900, dt_s: 1, drain_gj_per_s: 10 })
        expect(held.empty_at).toBeNull()
    })
})
