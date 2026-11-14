/**
 * Warp landing with interdiction bubbles, top-down 2D.
 *
 * A ship warping from `origin` to `destination` is pulled out of warp where its
 * warp line first enters a warp disruption sphere, and lands on that sphere's
 * edge. If the line never enters one, it lands on the destination (warp to 0).
 * Source: EVE University wiki, "Warp disruption field" / "Interdiction"
 * (https://wiki.eveuniversity.org/Warp_disruption_field): "ships warping
 * through the bubble are pulled out of warp at its edge".
 *
 * A ship already inside a bubble cannot start a warp; that is reported as
 * caught at the origin.
 */
import { add, distance, dot, scale, sub, type Vec2 } from './geometry'

/** Stargate activation range (m): a ship this close to the gate can jump. */
export const GATE_JUMP_RANGE_M = 2500

export interface Bubble {
    center: Vec2
    radius: number
}

export interface WarpLanding {
    landing: Vec2
    /** Distance from the landing point to the destination (m). */
    distance_to_destination: number
    /** True when a bubble pulled the ship out of warp. */
    caught: boolean
    /** Index of the bubble that caught it, or -1. */
    bubble_index: number
    /** Close enough to the destination gate to jump on landing. */
    in_jump_range: boolean
    /** How far the ship must burn to reach jump range (m), 0 when in range. */
    burn_to_jump_range: number
}

/**
 * Smallest t in [0, 1] where origin + t * (destination - origin) enters the
 * sphere, or null when the segment misses it.
 */
export function segment_entry(origin: Vec2, destination: Vec2, bubble: Bubble): number | null {
    const d = sub(destination, origin)
    const f = sub(origin, bubble.center)
    const a = dot(d, d)
    const c = dot(f, f) - bubble.radius * bubble.radius
    if (c <= 0) return 0 // starts inside
    if (a === 0) return null
    const b = 2 * dot(f, d)
    const discriminant = b * b - 4 * a * c
    if (discriminant < 0) return null
    const t = (-b - Math.sqrt(discriminant)) / (2 * a)
    return t >= 0 && t <= 1 ? t : null
}

export function warp_landing(origin: Vec2, destination: Vec2, bubbles: Bubble[]): WarpLanding {
    let best_t = Infinity
    let bubble_index = -1
    bubbles.forEach((bubble, index) => {
        const t = segment_entry(origin, destination, bubble)
        if (t !== null && t < best_t) {
            best_t = t
            bubble_index = index
        }
    })
    const landing = bubble_index >= 0 ? add(origin, scale(sub(destination, origin), best_t)) : destination
    const distance_to_destination = distance(landing, destination)
    return {
        landing,
        distance_to_destination,
        caught: bubble_index >= 0,
        bubble_index,
        in_jump_range: distance_to_destination <= GATE_JUMP_RANGE_M,
        burn_to_jump_range: Math.max(0, distance_to_destination - GATE_JUMP_RANGE_M),
    }
}

/** A catch that holds: pulled out of warp and still outside jump range. */
export const is_held = (landing: WarpLanding) => landing.caught && !landing.in_jump_range
