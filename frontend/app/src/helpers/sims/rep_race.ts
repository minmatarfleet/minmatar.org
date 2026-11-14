/**
 * The anchor's hit points while logi race the damage.
 *
 * Damage: a steady `dps` from t = 0, plus optional `alpha` volleys every
 * `alpha_every_s` starting at t = 0.
 * Repairs: each logi starts locking after `reaction_s` (how long until they
 * know who is primary: a broadcast is near-instant, spotting it on the
 * overview takes longer), lock completes after `lock_time_s`, and then every
 * repairer cycles. Armor repairs land at the END of each cycle; shield
 * repairs land at the start. Source: EVE University, "Remote armor repairer"
 * / "Logistics" (https://wiki.eveuniversity.org/Logistics_Ships) and
 * "Targeting" for lock time.
 *
 * Lock time (s) = 40000 / (scan_resolution * asinh(signature)^2).
 * Source: EVE University, "Targeting" (https://wiki.eveuniversity.org/Targeting#Lock_time).
 */

export function lock_time_s(scan_resolution_mm: number, target_signature_m: number): number {
    const a = Math.asinh(target_signature_m)
    return 40000 / (scan_resolution_mm * a * a)
}

export interface RepRaceInput {
    max_hp: number
    duration_s: number
    dps: number
    alpha?: number
    alpha_every_s?: number
    logi_count: number
    /** Repairers per logi ship. */
    reps_per_logi: number
    rep_amount: number
    rep_cycle_s: number
    lock_time_s: number
    reaction_s: number
    /** 'end' for armor (default), 'start' for shield. */
    lands_at?: 'start' | 'end'
    dt_s?: number
}

export interface RepRaceResult {
    series: { t: number, hp: number }[]
    survived: boolean
    died_at: number | null
    /** When the first repair landed, or null if none did in time. */
    first_rep_at: number | null
    lowest_hp: number
}

export function simulate_rep_race(input: RepRaceInput): RepRaceResult {
    const dt = input.dt_s ?? 0.25
    let hp = input.max_hp
    const series = [{ t: 0, hp }]
    let died_at: number | null = null
    let lowest = hp

    const reps_start = input.reaction_s + input.lock_time_s
    const lands_at_end = (input.lands_at ?? 'end') === 'end'
    const first_rep_at = input.logi_count > 0 && input.reps_per_logi > 0
        ? reps_start + (lands_at_end ? input.rep_cycle_s : 0)
        : null
    const rep_per_landing = input.logi_count * input.reps_per_logi * input.rep_amount

    // Event times on a grid of dt, so floating error never skips a landing.
    const on_grid = (x: number) => Math.round(x / dt)
    const landing_steps = new Set<number>()
    if (first_rep_at !== null)
        for (let t = first_rep_at; t <= input.duration_s + 1e-9; t += input.rep_cycle_s) landing_steps.add(on_grid(t))
    const alpha_steps = new Set<number>()
    if (input.alpha && input.alpha_every_s)
        for (let t = 0; t <= input.duration_s + 1e-9; t += input.alpha_every_s) alpha_steps.add(on_grid(t))

    const steps = on_grid(input.duration_s)
    for (let i = 0; i <= steps; i++) {
        const t = i * dt
        if (i > 0) hp -= input.dps * dt
        if (alpha_steps.has(i)) hp -= input.alpha ?? 0
        if (hp <= 0 && died_at === null) {
            died_at = Number(t.toFixed(6))
            hp = 0
            series.push({ t: died_at, hp })
            lowest = 0
            break
        }
        if (landing_steps.has(i)) hp = Math.min(input.max_hp, hp + rep_per_landing)
        lowest = Math.min(lowest, hp)
        if (i > 0) series.push({ t: Number(t.toFixed(6)), hp })
    }

    return { series, survived: died_at === null, died_at, first_rep_at, lowest_hp: lowest }
}
