import { describe, expect, it } from 'vitest'
import {
    APPLIED_DEFAULT, APPLIED_TARGETS, applied_scenario,
    BUBBLE_DEFAULT, BUBBLE_TARGETS, bubble_scenario,
    CAP_CURVE_DEFAULT, CAP_CURVE_TARGETS, cap_curve_scenario,
    JAM_DEFAULT, JAM_TARGETS, jam_scenario,
    MJFG_DEFAULT, MJFG_TARGETS, mjfg_scenario,
    NEUT_DEFAULT, NEUT_TARGETS, neut_scenario,
    REP_DEFAULT, REP_TARGETS, rep_scenario,
    SPREAD_DEFAULT, SPREAD_TARGETS, spread_scenario,
    type TargetSpec,
} from '@helpers/sims/scenarios'

/** Every target is met by at least one state, and no target is met by the default state. */
function reachable(targets: TargetSpec[], states: { met: Record<string, boolean> }[], initial: { met: Record<string, boolean> }) {
    for (const target of targets) {
        expect(states.some((s) => s.met[target.id]), target.id).toBe(true)
        expect(initial.met[target.id], `${target.id} is met at the start`).toBe(false)
    }
}

const range = (from: number, to: number, step: number) => Array.from({ length: Math.floor((to - from) / step) + 1 }, (_, i) => from + i * step)

describe('bubble scenario', () => {
    const states = range(-30, 80, 1).flatMap((along_km) => range(-40, 40, 1).map((off_km) => bubble_scenario({ along_km, off_km })))

    it('every target is reachable from the sliders', () => {
        reachable(BUBBLE_TARGETS, states, bubble_scenario(BUBBLE_DEFAULT))
    })

    it('reads out the three landing states', () => {
        expect(bubble_scenario({ along_km: 45, off_km: 0 }).readouts.sun).toBe('65 km off the gate. Caught, burns 63 km back')
        expect(bubble_scenario({ along_km: 0, off_km: 39 }).readouts.planet).toMatch(/km off the gate|On the gate/)
        expect(bubble_scenario({ along_km: -30, off_km: 0 }).readouts.sun).toBe('On the gate. Missed the bubble, jumps out')
        expect(bubble_scenario({ along_km: -18, off_km: 0 }).readouts.sun).toBe('Stopped inside 2.5 km jump range. Jumps out')
    })
})

describe('MJFG scenario', () => {
    it('every target is reachable', () => {
        const states = range(-5, 5, 0.5).flatMap((x_km) => range(-5, 5, 0.5).flatMap((y_km) => range(0, 345, 15).map((heading) => mjfg_scenario({ x_km, y_km, heading }))))
        reachable(MJFG_TARGETS, states, mjfg_scenario(MJFG_DEFAULT))
        expect(states.some((s) => s.met.all_free && s.met.near_beacon)).toBe(true)
    })

    it('never takes a scrammed ship', () => {
        expect(mjfg_scenario({ x_km: 5, y_km: -2, heading: 0 }).jumped.has('G')).toBe(false)
    })
})

describe('capacitor curve scenario', () => {
    it('every target is reachable', () => {
        const states = range(0, 100, 1).flatMap((level_percent) => range(0, 20, 0.25).map((drain_gjs) => cap_curve_scenario({ level_percent, drain_gjs })))
        reachable(CAP_CURVE_TARGETS, states, cap_curve_scenario(CAP_CURVE_DEFAULT))
    })
})

describe('neut pressure scenario', () => {
    const states = range(1, 6, 1).flatMap((neuts) => range(5, 40, 1).map((range_km) => ({ neuts, range_km, ...neut_scenario({ neuts, range_km }) })))

    it('every target is reachable', () => {
        reachable(NEUT_TARGETS, states, neut_scenario(NEUT_DEFAULT))
    })

    it('one neut never breaks the chain', () => {
        expect(states.filter((s) => s.neuts === 1).every((s) => !s.met.break)).toBe(true)
    })
})

describe('jam chance scenario', () => {
    it('only a Kitsune with a radar jammer clears 40% on a Guardian', () => {
        const kinds = ['radar', 'ladar', 'magnetometric', 'gravimetric', 'multispectral'] as const
        const states = (['griffin', 'kitsune'] as const).flatMap((ship) => kinds.map((kind) => jam_scenario({ ship, picks: { guardian: kind, scimitar: 'ladar', caracal: 'gravimetric' } })))
        reachable(JAM_TARGETS, states, jam_scenario(JAM_DEFAULT))
        const forty = states.filter((s) => s.met.forty_guardian)
        expect(forty).toHaveLength(1)
        expect(forty[0].rows[0].kind).toBe('radar')
    })
})

describe('ECM spread scenario', () => {
    it('only a full spread keeps two jammed', () => {
        const logi = ['A', 'B', 'C']
        const states = logi.flatMap((a) => logi.flatMap((b) => logi.map((c) => ({ assign: [a, b, c], ...spread_scenario({ assign: [a, b, c] }) }))))
        reachable(SPREAD_TARGETS, states, spread_scenario(SPREAD_DEFAULT))
        for (const s of states.filter((x) => x.met.two_jammed)) expect(new Set(s.assign).size).toBe(3)
    })
})

describe('rep race scenario', () => {
    it('every target is reachable and the broadcast matters', () => {
        const states = range(1, 5, 1).flatMap((logi) => (['broadcast', 'eyeball'] as const).map((call) => rep_scenario({ logi, call })))
        reachable(REP_TARGETS, states, rep_scenario(REP_DEFAULT))
        expect(rep_scenario({ logi: 2, call: 'broadcast' }).sim.survived).toBe(true)
        expect(rep_scenario({ logi: 2, call: 'eyeball' }).sim.survived).toBe(false)
    })
})

describe('applied damage scenario', () => {
    it('every target is reachable', () => {
        const ammo = ['republic_fleet_emp_l', 'barrage_l', 'nuclear_l', 'tremor_l'] as const
        const approaches = ['head_on', 'angled', 'orbit'] as const
        const states = ammo.flatMap((a) => approaches.flatMap((approach) => range(5, 90, 1).map((range_km) => applied_scenario({ ammo: a, approach, range_km }))))
        reachable(APPLIED_TARGETS, states, applied_scenario(APPLIED_DEFAULT))
    })

    it('Republic Fleet EMP L hits hardest per volley when it lands', () => {
        const emp = applied_scenario({ ammo: 'republic_fleet_emp_l', approach: 'head_on', range_km: 30 })
        const nuclear = applied_scenario({ ammo: 'nuclear_l', approach: 'head_on', range_km: 30 })
        expect(emp.volley).toBeGreaterThan(nuclear.volley)
    })
})
