/**
 * ECM jam chance and jammer spread.
 *
 * Per cycle, a jammer jams with probability min(1, jammer strength for the
 * target's sensor type / target sensor strength). A racial jammer is strong
 * against its own sensor type; a multispectral jammer has one (lower) strength
 * for every type. Source: EVE University, "Electronic warfare: ECM"
 * (https://wiki.eveuniversity.org/Electronic_warfare#ECM).
 *
 * Several jammers on one target: the target stays unjammed only if every
 * jammer misses, so P(jammed) = 1 - prod(1 - p_i). The expected number of
 * jammed targets is the sum of those over targets (linearity of expectation).
 */

export const SENSOR_TYPES = ['radar', 'ladar', 'magnetometric', 'gravimetric'] as const
export type SensorType = typeof SENSOR_TYPES[number]

export type JammerStrengths = Record<SensorType, number>

export interface EcmTarget {
    sensor_type: SensorType
    sensor_strength: number
}

/**
 * Rules since the 2018 ECM rework, as data for captions:
 * a jammed ship loses its locks but can still lock the ship that jammed it.
 */
export const ECM_RULES = {
    jammed_ship_can_lock_jammer: true,
    jam_lasts_one_cycle: true,
    source: 'EVE University, "Electronic warfare: ECM" (post-2018 rework)',
} as const

/** Jam chance for one jammer cycle, optionally scaled by range effectiveness (0..1). */
export function jam_chance(jammer: JammerStrengths, target: EcmTarget, effectiveness = 1): number {
    if (target.sensor_strength <= 0) return 1
    const strength = jammer[target.sensor_type] * effectiveness
    return Math.min(1, Math.max(0, strength / target.sensor_strength))
}

/** Jammer strength after a hull bonus of `percent_per_level` at `level`. */
export function bonused_strengths(jammer: JammerStrengths, percent_per_level: number, level = 5): JammerStrengths {
    const k = 1 + (percent_per_level * level) / 100
    return {
        radar: jammer.radar * k,
        ladar: jammer.ladar * k,
        magnetometric: jammer.magnetometric * k,
        gravimetric: jammer.gravimetric * k,
    }
}

/** Probability a target is jammed by independent jammers with chances `chances`. */
export function combined_jam_chance(chances: number[]): number {
    return 1 - chances.reduce((miss, p) => miss * (1 - Math.min(1, Math.max(0, p))), 1)
}

/**
 * Expected number of jammed targets. `chances_by_target[i]` lists the jam
 * chance of every jammer assigned to target i.
 */
export function expected_jammed(chances_by_target: number[][]): number {
    return chances_by_target.reduce((sum, chances) => sum + combined_jam_chance(chances), 0)
}

/** The sensor type a racial jammer is strongest against. */
export function strongest_sensor(jammer: JammerStrengths): SensorType {
    return SENSOR_TYPES.reduce((best, type) => (jammer[type] > jammer[best] ? type : best), SENSOR_TYPES[0])
}

/** The hull's sensor type: the one with non-zero strength (the largest if several). */
export function sensor_of(strengths: Record<SensorType, number>): EcmTarget {
    const type = strongest_sensor(strengths)
    return { sensor_type: type, sensor_strength: strengths[type] }
}
