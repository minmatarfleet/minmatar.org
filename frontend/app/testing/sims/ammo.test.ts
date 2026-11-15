import { describe, expect, it } from 'vitest'
import { existsSync } from 'node:fs'
import Database from 'better-sqlite3'

import ammo from '@/data/fleet-roles/ammo.json'
import { extract_ammo, extract_targets } from '../../scripts/extract_ammo_charts.mjs'

const SDE_PATHS = [process.env.SDE_PATH, 'src/data/sde-3409592.sqlite', 'src/data/sde-3316380.sqlite']
    .filter((path): path is string => Boolean(path))
const sde_path = SDE_PATHS.find((path) => existsSync(path))

const sqlite_loads = (() => {
    try {
        new Database(':memory:').close()
        return true
    } catch {
        return false
    }
})()

describe('ammo charts', () => {
    it('has the charges our doctrines carry', () => {
        const charges = ammo.charges as Record<string, Record<string, number | string>>
        expect(charges['Barrage L'].family).toBe('projectile')
        expect(charges['Barrage L'].falloff_mult).toBeGreaterThan(1)
        expect(charges['Scorch L'].family).toBe('laser')
        expect(charges['Scorch L'].range_mult).toBeGreaterThan(1)
        expect(charges['Scourge Fury Cruise Missile'].range_km).toBeGreaterThan(0)
    })

    it.runIf(Boolean(sde_path) && sqlite_loads)('matches the local SDE snapshot', () => {
        const db = new Database(sde_path as string, { readonly: true, fileMustExist: true })
        const charges = extract_ammo(db)
        const targets = extract_targets(db)
        db.close()
        expect(charges).toEqual(ammo.charges)
        expect(targets).toEqual(ammo.targets)
    })
})
