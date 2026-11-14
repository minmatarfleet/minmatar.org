/**
 * Dogma constants for the fleet-role simulators, generated from the SDE by
 * scripts/extract_role_sim_constants.mjs. Each entry in the JSON also records
 * the type and attribute (or hull trait) it came from.
 */
import data from '../../data/fleet-roles/sim_constants.json'

export type SimConstantKey = keyof typeof data.values

/** Plain numbers by key, e.g. SIM.probe_radius_km === 20. */
export const SIM = Object.fromEntries(
    Object.entries(data.values).map(([key, entry]) => [key, entry.value]),
) as Record<SimConstantKey, number>

/** "Warp Disrupt Probe: Warp Disruption Range", for captions and tooltips. */
export function sim_source(key: SimConstantKey): string {
    const entry = data.values[key] as { type_name: string, attribute_name?: string, trait_skill?: string }
    return `${entry.type_name}: ${entry.attribute_name ?? `${entry.trait_skill} trait`}`
}
