import { describe, expect, it } from 'vitest'
import { mjfg_jump } from '@helpers/sims/mjfg'

const base = { generator: { x: 0, y: 0 }, heading_degrees: 0, radius: 6000, jump_distance: 100000, max_ships: 24 }

describe('mjfg_jump', () => {
    it('moves every ship in range by the same vector along the heading', () => {
        const result = mjfg_jump({ ...base, heading_degrees: 90, ships: [{ id: 'a', position: { x: 1000, y: 2000 } }] })
        expect(result.generator_landing.x).toBeCloseTo(0, 6)
        expect(result.generator_landing.y).toBeCloseTo(100000, 6)
        expect(result.jumped[0].to.x).toBeCloseTo(1000, 6)
        expect(result.jumped[0].to.y).toBeCloseTo(102000, 6)
    })

    it('leaves ships out of range and scrammed ships behind', () => {
        const result = mjfg_jump({ ...base, ships: [
            { id: 'near', position: { x: 6000, y: 0 } },
            { id: 'far', position: { x: 6001, y: 0 } },
            { id: 'held', position: { x: 100, y: 0 }, scrammed: true },
        ] })
        expect(result.jumped.map((j) => j.id)).toEqual(['near'])
        expect(result.left_behind).toEqual([{ id: 'far', reason: 'out_of_range' }, { id: 'held', reason: 'scrammed' }])
    })

    it('takes at most max_ships, nearest first', () => {
        const ships = Array.from({ length: 5 }, (_, i) => ({ id: `s${i}`, position: { x: (5 - i) * 1000, y: 0 } }))
        const result = mjfg_jump({ ...base, max_ships: 3, ships })
        expect(result.jumped.map((j) => j.id)).toEqual(['s4', 's3', 's2'])
        expect(result.left_behind.filter((l) => l.reason === 'ship_cap')).toHaveLength(2)
    })

    it('does not activate when the generator is scrammed', () => {
        const result = mjfg_jump({ ...base, generator_scrammed: true, ships: [{ id: 'a', position: { x: 0, y: 0 } }] })
        expect(result.activated).toBe(false)
        expect(result.jumped).toEqual([])
    })
})
