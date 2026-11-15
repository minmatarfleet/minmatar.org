#!/usr/bin/env node
/**
 * Dogma constants the fleet-role guides quote in their text (data/fleet-roles/facts.ts).
 *
 * Reads the local SDE snapshot (resolved through src/helpers/sde_path.mjs, or
 * SDE_PATH) and writes src/data/fleet-roles/sim_constants.json. The JSON is
 * checked in so the site never needs the 550 MB SDE; testing/sims/
 * sim_constants.test.ts re-derives it when the SDE is present and fails if the
 * two drift.
 *
 * Every value records where it came from: the type, and either the dogma
 * attribute (dgmTypeAttributes) or the hull trait (invTraits) it was read from.
 * Values are looked up by attribute ID, because this Fuzzwork dump leaves
 * some attribute names empty; `attribute_name` falls back to the dogma name
 * written here when the SDE has none.
 *
 * Usage (from frontend/app):
 *   node scripts/extract_role_sim_constants.mjs
 *   SDE_PATH=/path/to/sde.sqlite node scripts/extract_role_sim_constants.mjs
 */
import { writeFileSync } from 'node:fs'
import { fileURLToPath, pathToFileURL } from 'node:url'
import path from 'node:path'
import Database from 'better-sqlite3'
import { resolve_sde_path } from '../src/helpers/sde_path.mjs'

export const OUTPUT_PATH = 'src/data/fleet-roles/sim_constants.json'

/**
 * @typedef {{ key: string, type: string, attribute_id: number, fallback_name: string, unit: string, scale?: number }} AttributeSpec
 * @typedef {{ key: string, type: string, trait: string, unit: string }} TraitSpec
 */

/** @param {string} key @param {string} type @param {number} attribute_id @param {string} fallback_name @param {string} unit @param {number} [scale] @returns {AttributeSpec} */
const a = (key, type, attribute_id, fallback_name, unit, scale) => ({ key, type, attribute_id, fallback_name, unit, ...(scale ? { scale } : {}) })

const M_TO_KM = 0.001
const MS_TO_S = 0.001

/** Hulls whose sensor strength, signature and capacitor the sims use. */
const HULLS = [
    ['guardian', 'Guardian'],
    ['scimitar', 'Scimitar'],
    ['typhoon', 'Typhoon'],
    ['vagabond', 'Vagabond'],
    ['caracal', 'Caracal'],
    ['rifter', 'Rifter'],
]

/** @type {AttributeSpec[]} */
export const ATTRIBUTES = [
    // Interdiction
    a('probe_radius_km', 'Warp Disrupt Probe', 103, 'warpScrambleRange', 'km', M_TO_KM),
    a('mobile_large_bubble_radius_km', 'Mobile Large Warp Disruptor I', 103, 'warpScrambleRange', 'km', M_TO_KM),
    a('hic_bubble_radius_km', 'Warp Disruption Field Generator II', 103, 'warpScrambleRange', 'km', M_TO_KM),
    a('hic_bubble_duration_s', 'Warp Disruption Field Generator II', 73, 'duration', 's', MS_TO_S),
    a('web_probe_radius_km', 'Stasis Webification Probe', 2279, 'doomsdayAOERange', 'km', M_TO_KM),
    a('web_probe_duration_s', 'Stasis Webification Probe', 2280, 'doomsdayAOEDuration', 's', MS_TO_S),
    a('web_probe_velocity_bonus_percent', 'Stasis Webification Probe', 20, 'speedFactor', '%'),

    // Micro Jump Field Generator
    a('mjfg_radius_km', 'Micro Jump Field Generator', 2067, 'mjdShipJumpRadius', 'km', M_TO_KM),
    a('mjfg_spool_s', 'Micro Jump Field Generator', 73, 'duration', 's', MS_TO_S),
    a('mjfg_distance_km', 'Micro Jump Field Generator', 2066, 'mjdJumpRange', 'km', M_TO_KM),
    a('mjfg_max_ships', 'Micro Jump Field Generator', 2832, 'mjfgRadius', 'ships'),
    a('mjfg_reactivation_s', 'Micro Jump Field Generator', 669, 'moduleReactivationDelay', 's', MS_TO_S),

    // Energy neutralizers
    a('heavy_neut_amount_gj', 'Heavy Energy Neutralizer II', 97, 'energyNeutralizerAmount', 'GJ'),
    a('heavy_neut_optimal_km', 'Heavy Energy Neutralizer II', 54, 'maxRange', 'km', M_TO_KM),
    a('heavy_neut_falloff_km', 'Heavy Energy Neutralizer II', 2044, 'falloffEffectiveness', 'km', M_TO_KM),
    a('heavy_neut_cycle_s', 'Heavy Energy Neutralizer II', 73, 'duration', 's', MS_TO_S),
    a('medium_neut_amount_gj', 'Medium Energy Neutralizer II', 97, 'energyNeutralizerAmount', 'GJ'),
    a('medium_neut_optimal_km', 'Medium Energy Neutralizer II', 54, 'maxRange', 'km', M_TO_KM),
    a('medium_neut_falloff_km', 'Medium Energy Neutralizer II', 2044, 'falloffEffectiveness', 'km', M_TO_KM),
    a('medium_neut_cycle_s', 'Medium Energy Neutralizer II', 73, 'duration', 's', MS_TO_S),

    // Logistics modules
    a('large_rar_amount_hp', 'Large Remote Armor Repairer II', 84, 'armorDamageAmount', 'HP'),
    a('large_rar_cycle_s', 'Large Remote Armor Repairer II', 73, 'duration', 's', MS_TO_S),
    a('large_rar_cap_gj', 'Large Remote Armor Repairer II', 6, 'capacitorNeed', 'GJ'),
    a('large_rar_optimal_km', 'Large Remote Armor Repairer II', 54, 'maxRange', 'km', M_TO_KM),
    a('large_rar_falloff_km', 'Large Remote Armor Repairer II', 2044, 'falloffEffectiveness', 'km', M_TO_KM),
    a('large_rct_amount_gj', 'Large Remote Capacitor Transmitter II', 90, 'powerTransferAmount', 'GJ'),
    a('large_rct_cycle_s', 'Large Remote Capacitor Transmitter II', 73, 'duration', 's', MS_TO_S),
    a('large_rct_cap_gj', 'Large Remote Capacitor Transmitter II', 6, 'capacitorNeed', 'GJ'),
    a('large_rct_optimal_km', 'Large Remote Capacitor Transmitter II', 54, 'maxRange', 'km', M_TO_KM),

    // ECM
    ...['gravimetric', 'ladar', 'magnetometric', 'radar'].flatMap((sensor, i) => [
        a(`multispectral_ecm_${sensor}_strength`, 'Multispectral ECM II', 238 + i, `scan${sensor}StrengthBonus`, 'points'),
        a(`ladar_ecm_${sensor}_strength`, 'Ladar ECM II', 238 + i, `scan${sensor}StrengthBonus`, 'points'),
        a(`radar_ecm_${sensor}_strength`, 'Radar ECM II', 238 + i, `scan${sensor}StrengthBonus`, 'points'),
        a(`gravimetric_ecm_${sensor}_strength`, 'Gravimetric ECM II', 238 + i, `scan${sensor}StrengthBonus`, 'points'),
        a(`magnetometric_ecm_${sensor}_strength`, 'Magnetometric ECM II', 238 + i, `scan${sensor}StrengthBonus`, 'points'),
    ]),
    a('multispectral_ecm_optimal_km', 'Multispectral ECM II', 54, 'maxRange', 'km', M_TO_KM),
    a('multispectral_ecm_falloff_km', 'Multispectral ECM II', 2044, 'falloffEffectiveness', 'km', M_TO_KM),
    a('multispectral_ecm_cycle_s', 'Multispectral ECM II', 73, 'duration', 's', MS_TO_S),
    a('racial_ecm_optimal_km', 'Ladar ECM II', 54, 'maxRange', 'km', M_TO_KM),
    a('racial_ecm_falloff_km', 'Ladar ECM II', 2044, 'falloffEffectiveness', 'km', M_TO_KM),
    a('racial_ecm_cycle_s', 'Ladar ECM II', 73, 'duration', 's', MS_TO_S),

    // Hulls
    ...HULLS.flatMap(([key, type]) => [
        a(`${key}_radar_strength`, type, 208, 'scanRadarStrength', 'points'),
        a(`${key}_ladar_strength`, type, 209, 'scanLadarStrength', 'points'),
        a(`${key}_magnetometric_strength`, type, 210, 'scanMagnetometricStrength', 'points'),
        a(`${key}_gravimetric_strength`, type, 211, 'scanGravimetricStrength', 'points'),
        a(`${key}_signature_m`, type, 552, 'signatureRadius', 'm'),
        a(`${key}_max_velocity_ms`, type, 37, 'maxVelocity', 'm/s'),
        a(`${key}_cap_gj`, type, 482, 'capacitorCapacity', 'GJ'),
        a(`${key}_cap_recharge_s`, type, 55, 'rechargeRate', 's', MS_TO_S),
        a(`${key}_armor_hp`, type, 265, 'armorHP', 'HP'),
        a(`${key}_shield_hp`, type, 263, 'shieldCapacity', 'HP'),
        a(`${key}_scan_resolution_mm`, type, 564, 'scanResolution', 'mm'),
    ]),

    // Turrets and ammo
    a('howitzer_1400_optimal_km', '1400mm Howitzer Artillery II', 54, 'maxRange', 'km', M_TO_KM),
    a('howitzer_1400_falloff_km', '1400mm Howitzer Artillery II', 158, 'falloff', 'km', M_TO_KM),
    a('howitzer_1400_tracking', '1400mm Howitzer Artillery II', 160, 'trackingSpeed', 'rad/s'),
    a('howitzer_1400_damage_multiplier', '1400mm Howitzer Artillery II', 64, 'damageMultiplier', 'x'),
    a('howitzer_1400_signature_resolution_m', '1400mm Howitzer Artillery II', 620, 'optimalSigRadius', 'm'),
    a('howitzer_1400_rate_of_fire_s', '1400mm Howitzer Artillery II', 51, 'speed', 's', MS_TO_S),
    ...[
        ['republic_fleet_emp_l', 'Republic Fleet EMP L'],
        ['hail_l', 'Hail L'],
        ['barrage_l', 'Barrage L'],
        ['nuclear_l', 'Nuclear L'],
        ['tremor_l', 'Tremor L'],
    ].flatMap(([key, type]) => [
        a(`${key}_range_multiplier`, type, 120, 'weaponRangeMultiplier', 'x'),
        a(`${key}_tracking_multiplier`, type, 244, 'trackingSpeedMultiplier', 'x'),
        a(`${key}_em_damage`, type, 114, 'emDamage', 'HP'),
        a(`${key}_explosive_damage`, type, 116, 'explosiveDamage', 'HP'),
        a(`${key}_kinetic_damage`, type, 117, 'kineticDamage', 'HP'),
        a(`${key}_thermal_damage`, type, 118, 'thermalDamage', 'HP'),
    ]),
    a('barrage_l_falloff_multiplier', 'Barrage L', 517, 'fallofMultiplier', 'x'),
    a('hail_l_falloff_multiplier', 'Hail L', 517, 'fallofMultiplier', 'x'),

    // Missiles
    a('cruise_launcher_rate_of_fire_s', 'Cruise Missile Launcher II', 51, 'speed', 's', MS_TO_S),
    ...[
        ['inferno_cruise', 'Inferno Cruise Missile'],
        ['inferno_fury_cruise', 'Inferno Fury Cruise Missile'],
        ['inferno_precision_cruise', 'Inferno Precision Cruise Missile'],
    ].flatMap(([key, type]) => [
        a(`${key}_thermal_damage`, type, 118, 'thermalDamage', 'HP'),
        a(`${key}_explosion_radius_m`, type, 654, 'aoeCloudSize', 'm'),
        a(`${key}_explosion_velocity_ms`, type, 653, 'aoeVelocity', 'm/s'),
        a(`${key}_drf`, type, 1353, 'aoeDamageReductionFactor', 'x'),
        a(`${key}_velocity_ms`, type, 37, 'maxVelocity', 'm/s'),
        a(`${key}_flight_time_s`, type, 281, 'explosionDelay', 's', MS_TO_S),
    ]),
]

/** @type {TraitSpec[]} Hull bonuses per skill level, matched on the trait text. */
export const TRAITS = [
    { key: 'griffin_ecm_strength_bonus_per_level', type: 'Griffin', trait: 'ECM Target Jammer</a> strength', unit: '%/level' },
    { key: 'kitsune_ecm_strength_bonus_per_level', type: 'Kitsune', trait: 'ECM Target Jammer</a> strength', unit: '%/level' },
    { key: 'guardian_rar_cap_reduction_per_level', type: 'Guardian', trait: 'Remote Armor Repairer</a> activation cost', unit: '%/level' },
    { key: 'guardian_rct_cap_reduction_per_level', type: 'Guardian', trait: 'Remote Capacitor Transmitter</a> activation cost', unit: '%/level' },
]

const round = (/** @type {number} */ value) => Number(value.toPrecision(10))

/**
 * Read every constant from an open SDE database.
 * @param {import('better-sqlite3').Database} db
 */
export function extract_role_sim_constants(db) {
    const type_id = db.prepare('SELECT typeID FROM invTypes WHERE typeName = ?')
    const attribute = db.prepare(
        `SELECT COALESCE(d.valueFloat, d.valueInt) AS value, t.attributeName AS name
           FROM dgmTypeAttributes d LEFT JOIN dgmAttributeTypes t USING (attributeID)
          WHERE d.typeID = ? AND d.attributeID = ?`,
    )
    const trait = db.prepare(
        `SELECT tr.bonus AS bonus, tr.bonusText AS text, s.typeName AS skill
           FROM invTraits tr LEFT JOIN invTypes s ON s.typeID = tr.skillID
          WHERE tr.typeID = ?`,
    )

    const id_of = (/** @type {string} */ name) => {
        const row = /** @type {{ typeID: number } | undefined} */ (type_id.get(name))
        if (!row) throw new Error(`SDE has no type named "${name}"`)
        return row.typeID
    }

    /** @type {Record<string, Record<string, unknown>>} */
    const values = {}
    for (const spec of ATTRIBUTES) {
        const id = id_of(spec.type)
        const row = /** @type {{ value: number, name: string | null } | undefined} */ (attribute.get(id, spec.attribute_id))
        if (!row) throw new Error(`${spec.type} has no attribute ${spec.attribute_id} (${spec.fallback_name})`)
        values[spec.key] = {
            value: round(row.value * (spec.scale ?? 1)),
            unit: spec.unit,
            type_id: id,
            type_name: spec.type,
            attribute_id: spec.attribute_id,
            attribute_name: row.name || spec.fallback_name,
            ...(spec.scale ? { sde_value: row.value } : {}),
        }
    }
    for (const spec of TRAITS) {
        const id = id_of(spec.type)
        const rows = /** @type {{ bonus: number, text: string, skill: string | null }[]} */ (trait.all(id))
        const row = rows.find((r) => r.text?.includes(spec.trait))
        if (!row) throw new Error(`${spec.type} has no trait matching "${spec.trait}"`)
        values[spec.key] = {
            value: round(row.bonus),
            unit: spec.unit,
            type_id: id,
            type_name: spec.type,
            trait_skill: row.skill,
            trait_text: row.text.replace(/<[^>]+>/g, ''),
        }
    }
    return values
}

function main() {
    const root = path.join(path.dirname(fileURLToPath(import.meta.url)), '..')
    const { path: sde_path, build } = resolve_sde_path({ root })
    const db = new Database(sde_path, { readonly: true, fileMustExist: true })
    const values = extract_role_sim_constants(db)
    db.close()
    const output = {
        generated_by: 'scripts/extract_role_sim_constants.mjs',
        sde_build: build,
        note: 'Generated from the SDE. Do not edit by hand; re-run the script.',
        values,
    }
    writeFileSync(path.join(root, OUTPUT_PATH), `${JSON.stringify(output, null, 4)}\n`)
    console.log(`Wrote ${Object.keys(values).length} constants to ${OUTPUT_PATH} from ${sde_path}`)
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href)
    main()
