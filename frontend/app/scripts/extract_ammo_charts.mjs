#!/usr/bin/env node
/**
 * Ammo numbers for the Damage guide's "Ammo our ships carry" charts.
 *
 * Reads every published turret and missile charge from the local SDE snapshot
 * (resolved through src/helpers/sde_path.mjs, or SDE_PATH) and writes
 * src/data/fleet-roles/ammo.json. The guide matches the charges in our
 * doctrine fits' cargo to these rows by name, so a new doctrine charge shows
 * up without editing anything. testing/sims/ammo.test.ts re-derives the file
 * when the SDE is present and fails if the two drift.
 *
 * Usage (from frontend/app):
 *   node scripts/extract_ammo_charts.mjs
 */
import { writeFileSync } from 'node:fs'
import { fileURLToPath, pathToFileURL } from 'node:url'
import path from 'node:path'
import Database from 'better-sqlite3'
import { resolve_sde_path } from '../src/helpers/sde_path.mjs'

export const OUTPUT_PATH = 'src/data/fleet-roles/ammo.json'

/** Charge group id -> weapon family. */
export const FAMILIES = {
    83: 'projectile', 372: 'projectile', 376: 'projectile',
    85: 'hybrid', 373: 'hybrid', 377: 'hybrid',
    86: 'laser', 374: 'laser', 375: 'laser',
    1987: 'disintegrator', 1989: 'disintegrator',
    384: 'light_missile', 653: 'light_missile',
    387: 'rocket', 648: 'rocket',
    385: 'heavy_missile', 655: 'heavy_missile',
    772: 'heavy_assault_missile', 654: 'heavy_assault_missile',
    386: 'cruise_missile', 656: 'cruise_missile',
    89: 'torpedo', 657: 'torpedo',
}

/** Dogma attribute ids. */
const ATTR = {
    em: 114, explosive: 116, kinetic: 117, thermal: 118,
    range_mult: 120, tracking_mult: 244, falloff_mult: 517,
    charge_size: 128, velocity: 37, flight_ms: 281, aoe_radius: 654, aoe_velocity: 653, drf: 1353,
}

const round = (/** @type {number} */ value) => Number(value.toPrecision(6))

/** Hulls the ammo charts show damage against: signature, speed and base armor resists. */
export const TARGET_HULLS = ['Typhoon', 'Apocalypse Navy Issue', 'Guardian']

/** @param {import('better-sqlite3').Database} db */
export function extract_targets(db) {
    const type = db.prepare('SELECT typeID FROM invTypes WHERE typeName = ?')
    const attrs = db.prepare('SELECT attributeID AS id, COALESCE(valueFloat, valueInt) AS value FROM dgmTypeAttributes WHERE typeID = ?')
    /** @type {Record<string, Record<string, unknown>>} */
    const targets = {}
    for (const name of TARGET_HULLS) {
        const row = /** @type {{ typeID: number } | undefined} */ (type.get(name))
        if (!row) throw new Error(`SDE has no type named "${name}"`)
        const v = Object.fromEntries((/** @type {{ id: number, value: number }[]} */ (attrs.all(row.typeID))).map((r) => [r.id, r.value]))
        targets[name] = {
            type_id: row.typeID,
            signature_m: round(v[552]),
            velocity_ms: round(v[37]),
            // Armor resists: 1 - damage resonance (attributes 267 EM, 270 thermal, 269 kinetic, 268 explosive).
            armor_resists: { em: round(1 - v[267]), thermal: round(1 - v[270]), kinetic: round(1 - v[269]), explosive: round(1 - v[268]) },
        }
    }
    return targets
}

/** @param {import('better-sqlite3').Database} db */
export function extract_ammo(db) {
    const groups = Object.keys(FAMILIES).map(Number)
    const types = /** @type {{ typeID: number, typeName: string, groupID: number }[]} */ (db.prepare(
        `SELECT typeID, typeName, groupID FROM invTypes
          WHERE published = 1 AND groupID IN (${groups.join(',')})
          ORDER BY typeName`,
    ).all())
    const attrs = db.prepare(
        `SELECT attributeID AS id, COALESCE(valueFloat, valueInt) AS value
           FROM dgmTypeAttributes WHERE typeID = ?`,
    )
    /** @type {Record<string, Record<string, number | string>>} */
    const charges = {}
    for (const type of types) {
        const rows = /** @type {{ id: number, value: number }[]} */ (attrs.all(type.typeID))
        const v = Object.fromEntries(rows.map((r) => [r.id, r.value]))
        const family = FAMILIES[/** @type {keyof typeof FAMILIES} */ (type.groupID)]
        const missile = family.endsWith('missile') || family === 'rocket' || family === 'torpedo'
        /** @type {Record<string, number | string>} */
        const row = {
            type_id: type.typeID,
            family,
            em: round(v[ATTR.em] ?? 0),
            thermal: round(v[ATTR.thermal] ?? 0),
            kinetic: round(v[ATTR.kinetic] ?? 0),
            explosive: round(v[ATTR.explosive] ?? 0),
        }
        if (v[ATTR.charge_size] !== undefined) row.size = v[ATTR.charge_size]
        if (missile) {
            row.range_km = round(((v[ATTR.velocity] ?? 0) * (v[ATTR.flight_ms] ?? 0)) / 1000 / 1000)
            row.explosion_radius_m = round(v[ATTR.aoe_radius] ?? 0)
            row.explosion_velocity_ms = round(v[ATTR.aoe_velocity] ?? 0)
            if (v[ATTR.drf] !== undefined) row.drf = round(v[ATTR.drf])
        } else {
            row.range_mult = round(v[ATTR.range_mult] ?? 1)
            row.tracking_mult = round(v[ATTR.tracking_mult] ?? 1)
            if (v[ATTR.falloff_mult] !== undefined) row.falloff_mult = round(v[ATTR.falloff_mult])
        }
        charges[type.typeName] = row
    }
    return charges
}

function main() {
    const root = path.join(path.dirname(fileURLToPath(import.meta.url)), '..')
    const { path: sde_path, build } = resolve_sde_path({ root })
    const db = new Database(sde_path, { readonly: true, fileMustExist: true })
    const charges = extract_ammo(db)
    const targets = extract_targets(db)
    db.close()
    const output = {
        generated_by: 'scripts/extract_ammo_charts.mjs',
        sde_build: build,
        note: 'Generated from the SDE. Do not edit by hand; re-run the script.',
        charges,
        targets,
    }
    writeFileSync(path.join(root, OUTPUT_PATH), `${JSON.stringify(output)}\n`)
    console.log(`Wrote ${Object.keys(charges).length} charges to ${OUTPUT_PATH} from ${sde_path}`)
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href)
    main()
