/**
 * Damage application: turrets and missiles.
 *
 * Turret chance to hit (current formula, signature resolution normalised to 40000):
 *   chance = 0.5 ^ ( ((angular * 40000) / (tracking * signature))^2
 *                  + (max(0, distance - optimal) / falloff)^2 )
 * Source: EVE University, "Turret mechanics"
 * (https://wiki.eveuniversity.org/Turret_mechanics#Hit_chance).
 *
 * Expected damage per shot relative to paper: a roll X in [0, 1) hits when
 * X < chance; X < 0.01 is a wrecking shot for 3x, otherwise the shot does
 * (X + 0.49)x. Integrating over X:
 *   chance >= 0.01: (chance^2 + 0.98 * chance + 0.0501) / 2
 *   chance <  0.01: 3 * chance
 * Source: EVE University, "Turret mechanics" (Damage).
 *
 * Missiles:
 *   damage = base * min(1, S / Er, ((S / Er) * (Ev / V)) ^ drf)
 * with S the target signature, V its speed, Er/Ev the explosion radius and
 * velocity and drf the damage reduction factor.
 * Source: EVE University, "Missile mechanics"
 * (https://wiki.eveuniversity.org/Missile_mechanics#Damage_formula).
 */

export interface TurretShot {
    /** Target speed (m/s) and the share of it that is transversal (0..1). */
    target_speed_ms: number
    transversal_fraction: number
    target_signature_m: number
    distance_m: number
    tracking: number
    optimal_m: number
    falloff_m: number
}

/** Angular velocity (rad/s) from transversal speed and distance. */
export function angular_velocity(transversal_ms: number, distance_m: number): number {
    return distance_m > 0 ? Math.abs(transversal_ms) / distance_m : Infinity
}

export function turret_hit_chance(shot: TurretShot): number {
    const angular = angular_velocity(shot.target_speed_ms * shot.transversal_fraction, shot.distance_m)
    const tracking_term = shot.tracking > 0 && shot.target_signature_m > 0
        ? (angular * 40000) / (shot.tracking * shot.target_signature_m)
        : Infinity
    const range_term = shot.falloff_m > 0 ? Math.max(0, shot.distance_m - shot.optimal_m) / shot.falloff_m : (shot.distance_m > shot.optimal_m ? Infinity : 0)
    const exponent = (Number.isFinite(tracking_term) ? tracking_term ** 2 : Infinity) + range_term ** 2
    if (!Number.isFinite(exponent)) return 0
    return 0.5 ** exponent
}

/** Expected damage multiplier per shot (1.015 at a 100% hit chance). */
export function turret_damage_multiplier(chance: number): number {
    const c = Math.min(1, Math.max(0, chance))
    if (c < 0.01) return 3 * c
    return (c * c + 0.98 * c + 0.0501) / 2
}

/** Applied fraction of paper DPS for a turret shot, capped at 1. */
export function turret_applied_fraction(shot: TurretShot): number {
    return Math.min(1, turret_damage_multiplier(turret_hit_chance(shot)))
}

export interface MissileHit {
    target_signature_m: number
    target_speed_ms: number
    explosion_radius_m: number
    explosion_velocity_ms: number
    drf: number
}

/** Applied fraction (0..1) of a missile's base damage. */
export function missile_applied_fraction(hit: MissileHit): number {
    if (hit.explosion_radius_m <= 0) return 1
    const sig_term = hit.target_signature_m / hit.explosion_radius_m
    const speed_term = hit.target_speed_ms > 0
        ? (sig_term * (hit.explosion_velocity_ms / hit.target_speed_ms)) ** hit.drf
        : Infinity
    return Math.max(0, Math.min(1, sig_term, speed_term))
}
