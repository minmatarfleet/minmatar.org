/**
 * Capacitor recharge and pressure (neutralizers, transfers, a module that needs cap).
 *
 * Recharge: dC/dt = (10 * Cmax / tau) * (sqrt(C/Cmax) - C/Cmax), peaking at
 * 25% capacitor (2.5 * Cmax / tau). Source: EVE University, "Capacitor"
 * (https://wiki.eveuniversity.org/Capacitor#Capacitor_recharge_rate).
 * With s = sqrt(C/Cmax) the equation becomes ds/dt = (5 / tau) * (1 - s), so
 * the exact step is s(t) = 1 - (1 - s0) * exp(-5t / tau). Using the closed form
 * means an empty capacitor still recharges (the Euler step would stick at 0).
 *
 * Range: effectiveness = 0.5 ^ ((max(0, d - optimal) / falloff) ^ 2), the
 * same curve EVE uses for neutralizer, remote repair and ECM "effectiveness
 * falloff". Source: EVE University, "Energy neutralizer"
 * (https://wiki.eveuniversity.org/Energy_neutralizers) and "Falloff".
 *
 * Timing assumptions: a neutralizer drains at the start of each cycle (all
 * neuts start together at t = 0, as on an FC's "neuts on" call); a capacitor
 * transfer and the module's own cost apply at the start of each cycle too.
 */

/** Recharge rate (GJ/s) at capacitor level `cap`. */
export function cap_recharge_rate(cap: number, cap_max: number, tau_s: number): number {
    if (cap_max <= 0 || tau_s <= 0) return 0
    const c = Math.min(1, Math.max(0, cap / cap_max))
    return ((10 * cap_max) / tau_s) * (Math.sqrt(c) - c)
}

/** Highest recharge rate (GJ/s), reached at 25% capacitor. */
export const peak_recharge_rate = (cap_max: number, tau_s: number) => (2.5 * cap_max) / tau_s

/**
 * Where the capacitor settles under a steady drain (fraction of cap_max), or
 * null when the drain beats the peak recharge rate and the capacitor empties.
 * Solves 10 * (s - s^2) * Cmax / tau = drain for the upper (stable) root s.
 */
export function stable_level(drain_gj_per_s: number, cap_max: number, tau_s: number): number | null {
    if (drain_gj_per_s <= 0) return 1
    const k = (drain_gj_per_s * tau_s) / (10 * cap_max)
    const disc = 1 - 4 * k
    if (disc < 0) return null
    const s = (1 + Math.sqrt(disc)) / 2
    return s * s
}

/** Capacitor after recharging for `dt_s` seconds with nothing drawing on it. */
export function step_capacitor(cap: number, cap_max: number, tau_s: number, dt_s: number): number {
    if (cap_max <= 0) return 0
    const s0 = Math.sqrt(Math.min(1, Math.max(0, cap / cap_max)))
    const s = 1 - (1 - s0) * Math.exp((-5 * dt_s) / tau_s)
    return cap_max * s * s
}

/** Range effectiveness multiplier for falloff-based modules. */
export function falloff_effectiveness(distance_m: number, optimal_m: number, falloff_m: number): number {
    const beyond = Math.max(0, distance_m - optimal_m)
    if (beyond === 0) return 1
    if (falloff_m <= 0) return 0
    return 0.5 ** ((beyond / falloff_m) ** 2)
}

export interface CycleModule {
    /** GJ per cycle. */
    amount: number
    cycle_s: number
    /** Number of identical modules running in sync. */
    count: number
}

export interface RangedModule extends CycleModule {
    optimal_m: number
    falloff_m: number
}

export interface CapPressureInput {
    cap_max: number
    recharge_s: number
    /** Starting level as a fraction of cap_max (default 1). */
    start_fraction?: number
    duration_s: number
    /** Time step for the series (default 0.5 s). */
    dt_s?: number
    neuts?: RangedModule[]
    range_m?: number
    /** Incoming capacitor transfers (GJ per cycle each). */
    transfers?: CycleModule[]
    /** Modules the target runs: each costs `amount` GJ per cycle and shuts off when it cannot pay. */
    modules?: CycleModule[]
    /** A steady drain (GJ/s), e.g. an averaged neut stream. */
    drain_gj_per_s?: number
}

export interface CapPressureResult {
    series: { t: number, cap: number }[]
    /** First time the capacitor hit 0, or null. */
    empty_at: number | null
    /** First time a module could not pay for its cycle, or null. */
    module_off_at: number | null
    failed_cycles: number
    lowest_fraction: number
}

const EPS = 1e-9

/** Simulate the target's capacitor for `duration_s`. */
export function simulate_cap_pressure(input: CapPressureInput): CapPressureResult {
    const dt = input.dt_s ?? 0.5
    const cap_max = input.cap_max
    let cap = cap_max * (input.start_fraction ?? 1)
    const range = input.range_m ?? 0
    const neuts = (input.neuts ?? []).map((n) => ({
        cycle_s: n.cycle_s,
        drain: n.amount * n.count * falloff_effectiveness(range, n.optimal_m, n.falloff_m),
    }))
    const transfers = input.transfers ?? []
    const modules = input.modules ?? []

    const series = [{ t: 0, cap }]
    let empty_at: number | null = null
    let module_off_at: number | null = null
    let failed_cycles = 0
    let lowest = cap / cap_max

    // A cycle fires when t crosses a multiple of its length (starting at t = 0).
    const fires = (t: number, cycle_s: number) => cycle_s > 0 && Math.abs(t / cycle_s - Math.round(t / cycle_s)) * cycle_s < dt / 2

    const steps = Math.round(input.duration_s / dt)
    for (let i = 0; i <= steps; i++) {
        const t = i * dt
        if (i > 0) {
            cap = step_capacitor(cap, cap_max, input.recharge_s, dt)
            cap = Math.max(0, cap - (input.drain_gj_per_s ?? 0) * dt)
        }

        for (const transfer of transfers)
            if (fires(t, transfer.cycle_s)) cap = Math.min(cap_max, cap + transfer.amount * transfer.count)
        for (const neut of neuts)
            if (fires(t, neut.cycle_s)) cap = Math.max(0, cap - neut.drain)
        for (const module of modules) {
            if (!fires(t, module.cycle_s)) continue
            for (let k = 0; k < module.count; k++) {
                if (cap + EPS >= module.amount) cap -= module.amount
                else {
                    failed_cycles += 1
                    if (module_off_at === null) module_off_at = t
                }
            }
        }

        cap = Math.max(0, cap)
        if (cap <= EPS && empty_at === null) empty_at = t
        lowest = Math.min(lowest, cap / cap_max)
        if (i > 0) series.push({ t: Number(t.toFixed(6)), cap })
    }

    return { series, empty_at, module_off_at, failed_cycles, lowest_fraction: lowest }
}
