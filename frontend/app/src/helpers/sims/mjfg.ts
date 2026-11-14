/**
 * Micro Jump Field Generator.
 *
 * When the spool-up ends, the generator ship and up to `max_ships` other ships
 * within `radius` of it jump `jump_distance` along the generator ship's heading.
 * Every ship moves by the same vector, so the formation keeps its shape.
 * Warp-scrambled ships do not jump, and a scrammed generator cannot activate.
 * Source: the module's SDE description ("teleports the user and up to 24
 * nearby ships ... 100km in the direction the ship is facing") and EVE
 * University, "Micro Jump Field Generator"
 * (https://wiki.eveuniversity.org/Micro_Jump_Field_Generator).
 *
 * Which ships go when more than `max_ships` are in range is not documented;
 * this takes the nearest first.
 */
import { add, distance, heading_vector, scale, type Vec2 } from './geometry'

export interface MjfgShip {
    id: string
    position: Vec2
    scrammed?: boolean
}

export interface MjfgInput {
    generator: Vec2
    /** Degrees counter-clockwise from +x. */
    heading_degrees: number
    generator_scrammed?: boolean
    ships: MjfgShip[]
    radius: number
    jump_distance: number
    max_ships: number
}

export type LeftBehindReason = 'out_of_range' | 'scrammed' | 'ship_cap' | 'generator_scrammed'

export interface MjfgResult {
    activated: boolean
    generator_landing: Vec2
    jumped: { id: string, from: Vec2, to: Vec2 }[]
    left_behind: { id: string, reason: LeftBehindReason }[]
}

export function mjfg_jump(input: MjfgInput): MjfgResult {
    const offset = scale(heading_vector(input.heading_degrees), input.jump_distance)
    if (input.generator_scrammed) {
        return {
            activated: false,
            generator_landing: input.generator,
            jumped: [],
            left_behind: input.ships.map((ship) => ({ id: ship.id, reason: 'generator_scrammed' as const })),
        }
    }

    const left_behind: MjfgResult['left_behind'] = []
    const candidates: { ship: MjfgShip, range: number }[] = []
    for (const ship of input.ships) {
        const range = distance(ship.position, input.generator)
        if (range > input.radius) left_behind.push({ id: ship.id, reason: 'out_of_range' })
        else if (ship.scrammed) left_behind.push({ id: ship.id, reason: 'scrammed' })
        else candidates.push({ ship, range })
    }
    candidates.sort((a, b) => a.range - b.range)
    const jumped = candidates.slice(0, input.max_ships).map(({ ship }) => ({
        id: ship.id,
        from: ship.position,
        to: add(ship.position, offset),
    }))
    for (const { ship } of candidates.slice(input.max_ships))
        left_behind.push({ id: ship.id, reason: 'ship_cap' })

    return { activated: true, generator_landing: add(input.generator, offset), jumped, left_behind }
}
