import { describe, expect, it } from 'vitest'
import { lock_time_s, simulate_rep_race } from '@helpers/sims/rep_race'

const base = { max_hp: 10000, duration_s: 60, dps: 0, logi_count: 1, reps_per_logi: 1, rep_amount: 500, rep_cycle_s: 6, lock_time_s: 2, reaction_s: 1 }

describe('lock_time_s', () => {
    it('follows 40000 / (scan res * asinh(sig)^2)', () => {
        expect(lock_time_s(385, 330)).toBeCloseTo(40000 / (385 * Math.asinh(330) ** 2), 12)
        expect(lock_time_s(385, 330)).toBeCloseTo(2.46, 2)
        expect(lock_time_s(385, 40)).toBeGreaterThan(lock_time_s(385, 330))
    })
})

describe('simulate_rep_race', () => {
    it('armor reps land at the end of the first cycle after reaction + lock', () => {
        const r = simulate_rep_race({ ...base, dps: 100 })
        expect(r.first_rep_at).toBe(9)
        const before = r.series.find((p) => p.t === 8.75)!.hp
        const after = r.series.find((p) => p.t === 9)!.hp
        expect(after).toBeGreaterThan(before)
    })

    it('shield reps land at the start of the cycle', () => {
        expect(simulate_rep_race({ ...base, lands_at: 'start' }).first_rep_at).toBe(3)
    })

    it('dies when damage outruns reps and survives when reps hold', () => {
        const dead = simulate_rep_race({ ...base, max_hp: 3000, dps: 400 })
        expect(dead.survived).toBe(false)
        expect(dead.died_at).toBeCloseTo(7.5, 6)
        const alive = simulate_rep_race({ ...base, max_hp: 6000, dps: 400, logi_count: 3, reps_per_logi: 2 })
        expect(alive.survived).toBe(true)
    })

    it('a late lock can lose an anchor that a quick one saves', () => {
        const input = { ...base, max_hp: 12000, dps: 600, logi_count: 2, reps_per_logi: 3, rep_amount: 512, lock_time_s: 2.46 }
        expect(simulate_rep_race({ ...input, reaction_s: 1 }).survived).toBe(true)
        expect(simulate_rep_race({ ...input, reaction_s: 7 }).survived).toBe(false)
    })

    it('alpha volleys land on their schedule and HP never exceeds max', () => {
        const r = simulate_rep_race({ ...base, alpha: 1000, alpha_every_s: 10, logi_count: 3 })
        expect(r.series[1].hp).toBe(9000)
        expect(Math.max(...r.series.map((p) => p.hp))).toBeLessThanOrEqual(10000)
    })
})
