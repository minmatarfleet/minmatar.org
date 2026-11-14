/**
 * The eight fleet-role simulator scenarios: state in, picture data, readout
 * and target checks out. Pure functions, so the tests can prove every target
 * is reachable. Module and hull numbers come from SIM (generated from the
 * SDE); the scenario numbers (anchor buffer, incoming damage, call delays)
 * are labelled where they are defined.
 */
import { warp_landing, is_held, GATE_JUMP_RANGE_M, type WarpLanding } from './bubbles'
import { heading_vector, distance, type Vec2 } from './geometry'
import { mjfg_jump, type MjfgResult } from './mjfg'
import { cap_recharge_rate, peak_recharge_rate, simulate_cap_pressure, stable_level } from './capacitor'
import { bonused_strengths, expected_jammed, jam_chance, combined_jam_chance, type JammerStrengths, type SensorType } from './ecm'
import { lock_time_s, simulate_rep_race } from './rep_race'
import { missile_applied_fraction, turret_damage_multiplier, turret_hit_chance } from './application'
import { SIM } from './constants'

export interface TargetSpec {
    id: string
    label: string
}

const KM = 1000
const km = (m: number) => m / KM
const round_km = (m: number) => Math.round(km(m))

// ---------------------------------------------------------------- bubbles

/** Warp-in origins are far away; only the direction matters. */
const FAR = 1e9
export const PLANET_ANGLE_DEGREES = 38
export const BUBBLE_ALONG_RANGE = { min: -30, max: 80 } as const
export const BUBBLE_OFF_RANGE = { min: -40, max: 40 } as const

export const BUBBLE_TARGETS: TargetSpec[] = [
    { id: 'catch_both', label: 'Catch both warp-ins with one bubble' },
    { id: 'drag_40', label: 'Drag Sun traffic 40 km or more off the gate' },
    { id: 'sun_not_planet', label: 'Catch Sun traffic but let Planet IV through' },
]

export interface BubbleState {
    /** Bubble centre along the Sun line, km from the gate toward the Sun. */
    along_km: number
    /** Bubble centre off the Sun line, km (positive toward Planet IV). */
    off_km: number
}

export function bubble_describe(landing: WarpLanding): string {
    if (!landing.caught) return 'On the gate. Missed the bubble, jumps out'
    if (landing.in_jump_range) return 'Stopped inside 2.5 km jump range. Jumps out'
    return `${round_km(landing.distance_to_destination)} km off the gate. Caught, burns ${round_km(landing.burn_to_jump_range)} km back`
}

export function bubble_scenario(state: BubbleState) {
    const gate: Vec2 = { x: 0, y: 0 }
    const sun_origin: Vec2 = { x: -FAR, y: 0 }
    const planet_dir = heading_vector(180 - PLANET_ANGLE_DEGREES)
    const planet_origin: Vec2 = { x: planet_dir.x * FAR, y: planet_dir.y * FAR }
    const bubble = { center: { x: -state.along_km * KM, y: state.off_km * KM }, radius: SIM.probe_radius_km * KM }
    const sun = warp_landing(sun_origin, gate, [bubble])
    const planet = warp_landing(planet_origin, gate, [bubble])
    return {
        bubble,
        sun,
        planet,
        planet_dir,
        readouts: { sun: bubble_describe(sun), planet: bubble_describe(planet) },
        met: {
            catch_both: is_held(sun) && is_held(planet),
            drag_40: is_held(sun) && sun.distance_to_destination >= 40 * KM,
            sun_not_planet: is_held(sun) && !is_held(planet),
        } as Record<string, boolean>,
    }
}

export const BUBBLE_DEFAULT: BubbleState = { along_km: 50, off_km: 30 }
export { GATE_JUMP_RANGE_M }

// ---------------------------------------------------------------- MJFG

export const MJFG_TARGETS: TargetSpec[] = [
    { id: 'all_free', label: 'Take every ship that is not scrammed' },
    { id: 'near_beacon', label: 'Land within 15 km of the safe beacon' },
]

/** Fleet layout around the anchor (km). Two ships are held by hostile scramblers. */
export const MJFG_SHIPS = [
    { id: 'A', position: { x: -3, y: 1 } },
    { id: 'B', position: { x: 1, y: 3 } },
    { id: 'C', position: { x: 3.5, y: -1 } },
    { id: 'D', position: { x: -1, y: -3.5 } },
    { id: 'E', position: { x: 4.5, y: 2.5 } },
    { id: 'F', position: { x: -4, y: -2 } },
    { id: 'G', position: { x: 4, y: -3.5 }, scrammed: true },
    { id: 'H', position: { x: 6, y: 0.5 }, scrammed: true },
]
export const MJFG_HOSTILES: Vec2 = { x: 30, y: 0 }
export const MJFG_BEACON: Vec2 = { x: -70.7, y: 70.7 }

export interface MjfgState {
    x_km: number
    y_km: number
    heading: number
}

export const MJFG_DEFAULT: MjfgState = { x_km: -3, y_km: 0, heading: 0 }

export function mjfg_scenario(state: MjfgState) {
    const to_m = (p: Vec2) => ({ x: p.x * KM, y: p.y * KM })
    const result: MjfgResult = mjfg_jump({
        generator: to_m({ x: state.x_km, y: state.y_km }),
        heading_degrees: state.heading,
        ships: MJFG_SHIPS.map((s) => ({ id: s.id, position: to_m(s.position), scrammed: s.scrammed })),
        radius: SIM.mjfg_radius_km * KM,
        jump_distance: SIM.mjfg_distance_km * KM,
        max_ships: SIM.mjfg_max_ships,
    })
    const free = MJFG_SHIPS.filter((s) => !s.scrammed).map((s) => s.id)
    const jumped = new Set(result.jumped.map((j) => j.id))
    const landing_km = { x: km(result.generator_landing.x), y: km(result.generator_landing.y) }
    const beacon_km = distance(landing_km, MJFG_BEACON)
    const hostiles_km = distance(landing_km, MJFG_HOSTILES)
    const taken = free.filter((id) => jumped.has(id)).length
    return {
        result,
        jumped,
        landing_km,
        beacon_km,
        hostiles_km,
        readout: `${taken} of ${free.length} free ships jump with you. Lands ${Math.round(beacon_km)} km from the beacon, ${Math.round(hostiles_km)} km from the hostiles.`,
        met: {
            all_free: free.every((id) => jumped.has(id)),
            near_beacon: beacon_km <= 15,
        } as Record<string, boolean>,
    }
}

// ---------------------------------------------------------------- capacitor curve

export const CAP_CURVE_TARGETS: TargetSpec[] = [
    { id: 'find_peak', label: 'Find the level where the capacitor recharges fastest' },
    { id: 'pin_under', label: 'Pick a drain the Guardian can never outrun' },
    { id: 'smallest', label: 'Do it within 0.5 GJ/s of the limit' },
]

export interface CapCurveState {
    level_percent: number
    drain_gjs: number
}

export const CAP_CURVE_DEFAULT: CapCurveState = { level_percent: 80, drain_gjs: 6 }
export const CAP_CURVE_SECONDS = 300

export function cap_curve_scenario(state: CapCurveState) {
    const cap_max = SIM.guardian_cap_gj
    const tau = SIM.guardian_cap_recharge_s
    const peak = peak_recharge_rate(cap_max, tau)
    const rate = cap_recharge_rate((state.level_percent / 100) * cap_max, cap_max, tau)
    const settles = stable_level(state.drain_gjs, cap_max, tau)
    const trace = simulate_cap_pressure({ cap_max, recharge_s: tau, duration_s: CAP_CURVE_SECONDS, dt_s: 2, drain_gj_per_s: state.drain_gjs })
    const curve = Array.from({ length: 51 }, (_, i) => ({ level: i * 2, rate: cap_recharge_rate((i / 50) * cap_max, cap_max, tau) }))
    const beats = state.drain_gjs > peak
    return {
        cap_max,
        tau,
        peak,
        rate,
        settles,
        trace: trace.series,
        curve,
        readout: `At ${state.level_percent}% the Guardian recharges ${rate.toFixed(1)} GJ/s (peak ${peak.toFixed(2)} GJ/s at 25%). `
            + (settles === null
                ? `A ${state.drain_gjs} GJ/s drain beats the peak: it runs dry and stays dry.`
                : `A ${state.drain_gjs} GJ/s drain settles at ${Math.round(settles * 100)}%.`),
        met: {
            find_peak: Math.abs(state.level_percent - 25) <= 2,
            pin_under: beats,
            smallest: beats && state.drain_gjs - peak <= 0.5,
        } as Record<string, boolean>,
    }
}

// ---------------------------------------------------------------- neut pressure

export const NEUT_TARGETS: TargetSpec[] = [
    { id: 'break', label: 'Shut off the Guardian\'s repairers inside 60 s' },
    { id: 'break_far', label: 'Do it from 28 km or further' },
    { id: 'break_two', label: 'Do it with only two neuts' },
]

export interface NeutState {
    neuts: number
    range_km: number
}

export const NEUT_DEFAULT: NeutState = { neuts: 1, range_km: 15 }
export const NEUT_SECONDS = 60
/** Scenario fit: the target Guardian runs three repairers and one transmitter to its partner, Logistics Cruisers V. */
export const NEUT_TARGET_REPAIRERS = 3

export function neut_scenario(state: NeutState) {
    const level = 5
    const rar_cost = SIM.large_rar_cap_gj * (1 - (SIM.guardian_rar_cap_reduction_per_level * level) / 100)
    const rct_cost = SIM.large_rct_cap_gj * (1 - (SIM.guardian_rct_cap_reduction_per_level * level) / 100)
    const sim = simulate_cap_pressure({
        cap_max: SIM.guardian_cap_gj,
        recharge_s: SIM.guardian_cap_recharge_s,
        duration_s: NEUT_SECONDS,
        dt_s: 0.5,
        range_m: state.range_km * KM,
        neuts: [{
            amount: SIM.heavy_neut_amount_gj,
            cycle_s: SIM.heavy_neut_cycle_s,
            count: state.neuts,
            optimal_m: SIM.heavy_neut_optimal_km * KM,
            falloff_m: SIM.heavy_neut_falloff_km * KM,
        }],
        transfers: [{ amount: SIM.large_rct_amount_gj, cycle_s: SIM.large_rct_cycle_s, count: 1 }],
        modules: [
            { amount: rar_cost, cycle_s: SIM.large_rar_cycle_s, count: NEUT_TARGET_REPAIRERS },
            { amount: rct_cost, cycle_s: SIM.large_rct_cycle_s, count: 1 },
        ],
    })
    const effectiveness = state.range_km <= SIM.heavy_neut_optimal_km
        ? 1
        : 0.5 ** (((state.range_km - SIM.heavy_neut_optimal_km) / SIM.heavy_neut_falloff_km) ** 2)
    const broke = sim.module_off_at !== null
    return {
        sim,
        effectiveness,
        rar_cost,
        rct_cost,
        readout: (broke
            ? `Repairers shut off at ${sim.module_off_at} s.`
            : `The chain holds: lowest point ${Math.round(sim.lowest_fraction * 100)}%.`)
            + ` Each neut drains ${Math.round(SIM.heavy_neut_amount_gj * effectiveness)} GJ per cycle at ${state.range_km} km.`,
        met: {
            break: broke,
            break_far: broke && state.range_km >= 28,
            break_two: broke && state.neuts <= 2,
        } as Record<string, boolean>,
    }
}

// ---------------------------------------------------------------- jam chance

export type JammerKind = SensorType | 'multispectral'
export const JAMMER_KINDS: JammerKind[] = ['radar', 'ladar', 'magnetometric', 'gravimetric', 'multispectral']

export function jammer_strengths(kind: JammerKind): JammerStrengths {
    const key = (sensor: SensorType) => SIM[`${kind}_ecm_${sensor}_strength` as keyof typeof SIM]
    return { radar: key('radar'), ladar: key('ladar'), magnetometric: key('magnetometric'), gravimetric: key('gravimetric') }
}

export const JAM_HULLS = [
    { id: 'guardian', name: 'Guardian', sensor_type: 'radar' as SensorType, sensor_strength: SIM.guardian_radar_strength },
    { id: 'scimitar', name: 'Scimitar', sensor_type: 'ladar' as SensorType, sensor_strength: SIM.scimitar_ladar_strength },
    { id: 'caracal', name: 'Caracal', sensor_type: 'gravimetric' as SensorType, sensor_strength: SIM.caracal_gravimetric_strength },
]

export const JAM_SHIPS = {
    griffin: { name: 'Griffin', bonus: SIM.griffin_ecm_strength_bonus_per_level },
    kitsune: { name: 'Kitsune', bonus: SIM.kitsune_ecm_strength_bonus_per_level },
} as const
export type JamShip = keyof typeof JAM_SHIPS

export const JAM_TARGETS: TargetSpec[] = [
    { id: 'right_racial', label: 'Fit the matching racial jammer for all three hulls' },
    { id: 'forty_guardian', label: 'Get a 40% or better jam chance on the Guardian' },
]

export interface JamState {
    ship: JamShip
    picks: Record<string, JammerKind>
}

export const JAM_DEFAULT: JamState = { ship: 'griffin', picks: { guardian: 'multispectral', scimitar: 'multispectral', caracal: 'multispectral' } }

export function jam_scenario(state: JamState) {
    const bonus = JAM_SHIPS[state.ship].bonus
    const rows = JAM_HULLS.map((hull) => {
        const kind = state.picks[hull.id] ?? 'multispectral'
        const chance = jam_chance(bonused_strengths(jammer_strengths(kind), bonus, 5), hull)
        return { ...hull, kind, chance, matches: kind === hull.sensor_type }
    })
    return {
        rows,
        readout: rows.map((r) => `${r.name}: ${Math.round(r.chance * 100)}%`).join(', ') + ` per cycle from a ${JAM_SHIPS[state.ship].name} (Caldari Frigate V).`,
        met: {
            right_racial: rows.every((r) => r.matches),
            forty_guardian: (rows.find((r) => r.id === 'guardian')?.chance ?? 0) >= 0.4,
        } as Record<string, boolean>,
    }
}

// ---------------------------------------------------------------- ECM spread

export const SPREAD_TARGETS: TargetSpec[] = [
    { id: 'two_jammed', label: 'Keep two or more Scimitars jammed on average' },
    { id: 'stack_lesson', label: 'Stack every Kitsune on one Scimitar and see what it costs' },
]

/** Three Kitsunes, each with two Ladar ECM II, against three Scimitars. */
export const SPREAD_JAMMERS_PER_SHIP = 2
export const SPREAD_LOGI = ['A', 'B', 'C'] as const

export interface SpreadState {
    assign: string[]
}

export const SPREAD_DEFAULT: SpreadState = { assign: ['A', 'A', 'B'] }

export function spread_scenario(state: SpreadState) {
    const strengths = bonused_strengths(jammer_strengths('ladar'), SIM.kitsune_ecm_strength_bonus_per_level, 5)
    const p = jam_chance(strengths, { sensor_type: 'ladar', sensor_strength: SIM.scimitar_ladar_strength })
    const by_target = SPREAD_LOGI.map((logi) => {
        const ships = state.assign.filter((a) => a === logi).length
        return Array.from({ length: ships * SPREAD_JAMMERS_PER_SHIP }, () => p)
    })
    const per_logi = by_target.map((chances) => combined_jam_chance(chances))
    const expected = expected_jammed(by_target)
    const stacked = new Set(state.assign).size === 1
    return {
        p,
        per_logi,
        expected,
        readout: `Each jammer: ${Math.round(p * 100)}% per cycle. Expected Scimitars jammed: ${expected.toFixed(2)} of 3.`,
        met: {
            two_jammed: expected >= 2,
            stack_lesson: stacked,
        } as Record<string, boolean>,
    }
}

// ---------------------------------------------------------------- rep race

export const REP_TARGETS: TargetSpec[] = [
    { id: 'alive_broadcast', label: 'Keep the anchor alive for 60 s, repping from broadcasts' },
    { id: 'two_logi', label: 'Do it with only two Guardians' },
    { id: 'eyeball_loss', label: 'Watch two Guardians lose the anchor when nobody broadcasts' },
]

/** Scenario numbers: the anchor's armor buffer and the damage getting through its resists. */
export const REP_ANCHOR_HP = 12000
export const REP_INCOMING_DPS = 600
/** Scenario numbers: seconds before logi start locking. */
export const REP_REACTION_S = { broadcast: 1, eyeball: 7 } as const
export const REP_REPAIRERS_PER_LOGI = 3
export const REP_SECONDS = 60

export interface RepState {
    logi: number
    call: 'broadcast' | 'eyeball'
}

export const REP_DEFAULT: RepState = { logi: 1, call: 'broadcast' }

export function rep_scenario(state: RepState) {
    const lock = lock_time_s(SIM.guardian_scan_resolution_mm, SIM.typhoon_signature_m)
    const sim = simulate_rep_race({
        max_hp: REP_ANCHOR_HP,
        duration_s: REP_SECONDS,
        dps: REP_INCOMING_DPS,
        logi_count: state.logi,
        reps_per_logi: REP_REPAIRERS_PER_LOGI,
        rep_amount: SIM.large_rar_amount_hp,
        rep_cycle_s: SIM.large_rar_cycle_s,
        lock_time_s: lock,
        reaction_s: REP_REACTION_S[state.call],
    })
    return {
        sim,
        lock,
        readout: (sim.survived
            ? `The anchor lives: lowest ${Math.round((sim.lowest_hp / REP_ANCHOR_HP) * 100)}% armor.`
            : `The anchor dies at ${Math.round(sim.died_at ?? 0)} s.`)
            + ` First repair lands at ${(sim.first_rep_at ?? 0).toFixed(1)} s (call ${REP_REACTION_S[state.call]} s + lock ${lock.toFixed(1)} s + cycle ${SIM.large_rar_cycle_s} s).`,
        met: {
            alive_broadcast: sim.survived && state.call === 'broadcast',
            two_logi: sim.survived && state.call === 'broadcast' && state.logi <= 2,
            eyeball_loss: !sim.survived && state.call === 'eyeball' && state.logi === 2,
        } as Record<string, boolean>,
    }
}

// ---------------------------------------------------------------- applied damage

export const AMMO = {
    republic_fleet_emp_l: { name: 'Republic Fleet EMP L', falloff: 1 },
    barrage_l: { name: 'Barrage L', falloff: SIM.barrage_l_falloff_multiplier },
    nuclear_l: { name: 'Nuclear L', falloff: 1 },
    tremor_l: { name: 'Tremor L', falloff: 1 },
} as const
export type AmmoId = keyof typeof AMMO

export const APPROACHES = {
    head_on: { label: 'Head-on', transversal: 0.1 },
    angled: { label: 'Angled', transversal: 0.5 },
    orbit: { label: 'Orbiting', transversal: 1 },
} as const
export type ApproachId = keyof typeof APPROACHES

export const APPLIED_TARGETS: TargetSpec[] = [
    { id: 'land_75', label: 'Land 75% or more of paper damage on the Vagabond' },
    { id: 'emp_75', label: 'Do it with Republic Fleet EMP L' },
    { id: 'angled_50', label: 'Land 50% on an angled approach' },
]

export interface AppliedState {
    ammo: AmmoId
    range_km: number
    approach: ApproachId
}

export const APPLIED_DEFAULT: AppliedState = { ammo: 'republic_fleet_emp_l', range_km: 70, approach: 'orbit' }

const ammo_value = (ammo: AmmoId, field: string) => SIM[`${ammo}_${field}` as keyof typeof SIM]

export function applied_scenario(state: AppliedState) {
    const optimal_m = SIM.howitzer_1400_optimal_km * KM * ammo_value(state.ammo, 'range_multiplier')
    const falloff_m = SIM.howitzer_1400_falloff_km * KM * AMMO[state.ammo].falloff
    const tracking = SIM.howitzer_1400_tracking * ammo_value(state.ammo, 'tracking_multiplier')
    const chance = turret_hit_chance({
        target_speed_ms: SIM.vagabond_max_velocity_ms,
        transversal_fraction: APPROACHES[state.approach].transversal,
        target_signature_m: SIM.vagabond_signature_m,
        distance_m: state.range_km * KM,
        tracking,
        optimal_m,
        falloff_m,
    })
    const multiplier = turret_damage_multiplier(chance)
    const applied = Math.min(1, multiplier)
    const base = ['em', 'explosive', 'kinetic', 'thermal'].reduce((sum, type) => sum + ammo_value(state.ammo, `${type}_damage`), 0)
    const volley = base * SIM.howitzer_1400_damage_multiplier * multiplier
    const missile = missile_applied_fraction({
        target_signature_m: SIM.vagabond_signature_m,
        target_speed_ms: SIM.vagabond_max_velocity_ms,
        explosion_radius_m: SIM.inferno_precision_cruise_explosion_radius_m,
        explosion_velocity_ms: SIM.inferno_precision_cruise_explosion_velocity_ms,
        drf: SIM.inferno_precision_cruise_drf,
    })
    return {
        chance,
        applied,
        volley,
        optimal_km: km(optimal_m),
        falloff_km: km(falloff_m),
        missile,
        readout: `${Math.round(chance * 100)}% hit chance, ${Math.round(applied * 100)}% of paper damage, about ${Math.round(volley)} per gun per volley. `
            + `Optimal ${km(optimal_m).toFixed(1)} km + falloff ${km(falloff_m).toFixed(1)} km.`,
        met: {
            land_75: applied >= 0.75,
            emp_75: applied >= 0.75 && state.ammo === 'republic_fleet_emp_l',
            angled_50: applied >= 0.5 && state.approach === 'angled',
        } as Record<string, boolean>,
    }
}
