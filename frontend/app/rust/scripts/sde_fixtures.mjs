#!/usr/bin/env node
/**
 * Real SDE rows for the Rust "EVE/SDE" stories.
 *
 * Reads a small, fixed set of ships, modules and solar systems from the local
 * SDE snapshot (resolved through src/helpers/sde_path.mjs, or SDE_PATH) and
 * writes rust/fixtures/sde.json in the shapes of src/types/sde.ts. The JSON is
 * committed, so Storybook and the story tests never need the 550 MB snapshot;
 * rerun this after an SDE upgrade and review the diff.
 *
 * Usage (from frontend/app):
 *   node rust/scripts/sde_fixtures.mjs
 *   SDE_PATH=/path/to/sde.sqlite node rust/scripts/sde_fixtures.mjs
 */
import { writeFileSync, mkdirSync } from 'node:fs'
import path from 'node:path'
import Database from 'better-sqlite3'
import { resolve_sde_path } from '../../src/helpers/sde_path.mjs'

export const OUTPUT_PATH = 'rust/fixtures/sde.json'

/** Minmatar T1 hulls frigate to battleship, then T2, T3 and faction hulls. */
export const SHIPS = [
    'Rifter', 'Breacher', 'Thrasher', 'Stabber', 'Rupture', 'Hurricane', 'Cyclone', 'Tempest', 'Typhoon',
    'Jaguar', 'Wolf', 'Claw', 'Sabre', 'Vagabond', 'Muninn', 'Scimitar', 'Vargur', 'Svipul',
    'Republic Fleet Firetail', 'Stabber Fleet Issue', 'Hurricane Fleet Issue', 'Cynabal',
]

/** Modules spanning every meta group a fit shows. */
export const MODULES = [
    '200mm AutoCannon I', '200mm AutoCannon II', 'Republic Fleet 200mm Autocannon', "Ramaku's Modified 200mm AutoCannon",
    'Gyrostabilizer II', 'Republic Fleet Gyrostabilizer', "'Kindred' Gyrostabilizer",
    'Damage Control II', '5MN Microwarpdrive II', 'Gistii B-Type 5MN Microwarpdrive',
    'Warp Scrambler II', 'Domination Warp Scrambler', "'Delineative' Warp Scrambler",
    "Tobias' Modified Heavy Warp Scrambler", 'Loki Offensive - Launcher Efficiency Configuration',
]

/** Every security band: high-sec hubs, the Minmatar warzone, the 0.0–0.05 edge, null-sec and J-space. */
export const SYSTEMS = [
    'Amarr', 'Jita', 'Rens', 'Hek', 'Abudban', 'Teonusude', 'Uedama',
    'Amamake', 'Huola', 'Auga', 'Vard', 'Old Man Star', 'Tama', 'Evati', 'Arnstur', 'Egbinger',
    'HED-GP', '1DQ1-A', 'J164104', 'Thera',
]

const SLOT_ATTRIBUTES = { high: 14, mid: 13, low: 12, rig: 1137, subsystem: 1367, turrets: 102, launchers: 101 }

function by_name(rows, names, key) {
    const index = new Map(rows.map((row) => [row[key], row]))
    const missing = names.filter((name) => !index.has(name))
    if (missing.length > 0)
        throw new Error(`Not in this SDE snapshot: ${missing.join(', ')}`)
    return names.map((name) => index.get(name))
}

export function extract_types(db, names) {
    const placeholders = names.map(() => '?').join(',')
    const rows = db.prepare(`
        SELECT t.typeID AS type_id, t.typeName AS type_name, g.groupID AS group_id, g.groupName AS group_name,
               c.categoryID AS category_id, c.categoryName AS category_name,
               mg.metaGroupID AS meta_group_id, mg.metaGroupName AS meta_group_name
        FROM invTypes t
        JOIN invGroups g ON g.groupID = t.groupID
        JOIN invCategories c ON c.categoryID = g.categoryID
        LEFT JOIN invMetaTypes mt ON mt.typeID = t.typeID
        LEFT JOIN invMetaGroups mg ON mg.metaGroupID = mt.metaGroupID
        WHERE t.published = 1 AND t.typeName IN (${placeholders})
    `).all(...names)

    const types = by_name(rows, names, 'type_name').map((row) => ({ ...row }))

    const ships = types.filter((type) => type.category_id === 6)
    if (ships.length > 0) {
        const attribute_ids = Object.values(SLOT_ATTRIBUTES)
        const values = db.prepare(`
            SELECT typeID AS type_id, attributeID AS attribute_id, coalesce(valueFloat, valueInt, 0) AS value
            FROM dgmTypeAttributes
            WHERE typeID IN (${ships.map(() => '?').join(',')}) AND attributeID IN (${attribute_ids.map(() => '?').join(',')})
        `).all(...ships.map((ship) => ship.type_id), ...attribute_ids)

        for (const ship of ships) {
            ship.slots = { high: 0, mid: 0, low: 0, rig: 0, subsystem: 0, turrets: 0, launchers: 0 }
            for (const row of values.filter((value) => value.type_id === ship.type_id)) {
                const key = Object.keys(SLOT_ATTRIBUTES).find((name) => SLOT_ATTRIBUTES[name] === row.attribute_id)
                if (key)
                    ship.slots[key] = Math.round(row.value)
            }
        }
    }
    return types
}

export function extract_systems(db, names) {
    const rows = db.prepare(`
        SELECT s.solarSystemID AS system_id, s.solarSystemName AS system_name, s.security AS security,
               s.sunTypeID AS sun_type_id, c.constellationID AS constellation_id, c.constellationName AS constellation_name,
               r.regionID AS region_id, r.regionName AS region_name
        FROM mapSolarSystems s
        JOIN mapConstellations c ON c.constellationID = s.constellationID
        JOIN mapRegions r ON r.regionID = s.regionID
        WHERE s.solarSystemName IN (${names.map(() => '?').join(',')})
    `).all(...names)

    return by_name(rows, names, 'system_name').map((row) => ({
        ...row,
        // Four decimals keep every display rounding edge and a readable diff.
        security: Math.round(row.security * 10000) / 10000,
    }))
}

function main() {
    const { path: sde_path, build } = resolve_sde_path()
    const db = new Database(sde_path, { readonly: true, fileMustExist: true })
    const fixtures = {
        sde_build: build,
        ships: extract_types(db, SHIPS),
        modules: extract_types(db, MODULES),
        systems: extract_systems(db, SYSTEMS),
    }
    db.close()

    mkdirSync(path.dirname(OUTPUT_PATH), { recursive: true })
    writeFileSync(OUTPUT_PATH, `${JSON.stringify(fixtures, null, 2)}\n`)
    console.log(`Wrote ${OUTPUT_PATH}: ${fixtures.ships.length} ships, ${fixtures.modules.length} modules, ${fixtures.systems.length} systems (SDE build ${build ?? 'from SDE_PATH'}).`)
}

main()
