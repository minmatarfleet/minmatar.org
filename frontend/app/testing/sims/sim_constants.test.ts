import { describe, expect, it } from 'vitest'
import { existsSync } from 'node:fs'
import Database from 'better-sqlite3'

import constants from '@/data/fleet-roles/sim_constants.json'
import { SIM } from '@helpers/sims/constants'
import { extract_role_sim_constants } from '../../scripts/extract_role_sim_constants.mjs'

const SDE_PATHS = [process.env.SDE_PATH, 'src/data/sde-3409592.sqlite', 'src/data/sde-3316380.sqlite']
    .filter((path): path is string => Boolean(path))
const sde_path = SDE_PATHS.find((path) => existsSync(path))

/** better-sqlite3 is native; a node_modules built for another Node version cannot open anything. */
const sqlite_loads = (() => {
    try {
        new Database(':memory:').close()
        return true
    } catch {
        return false
    }
})()

describe('sim constants', () => {
    it('carries the values the guides quote', () => {
        expect(SIM.probe_radius_km).toBe(20)
        expect(SIM.mjfg_radius_km).toBe(6)
        expect(SIM.mjfg_distance_km).toBe(100)
        expect(SIM.mjfg_spool_s).toBeGreaterThan(0)
        expect(SIM.hic_bubble_radius_km).toBeGreaterThan(0)
        expect(SIM.web_probe_radius_km).toBeGreaterThan(0)
    })

    it('records a source for every value', () => {
        for (const [key, entry] of Object.entries(constants.values)) {
            const source = entry as Record<string, unknown>
            expect(source.type_name, key).toBeTruthy()
            expect(source.attribute_name ?? source.trait_text, key).toBeTruthy()
        }
    })

    it.runIf(Boolean(sde_path) && sqlite_loads)('matches the local SDE snapshot', () => {
        const db = new Database(sde_path as string, { readonly: true, fileMustExist: true })
        const values = extract_role_sim_constants(db)
        db.close()
        expect(values).toEqual(constants.values)
    })
})
