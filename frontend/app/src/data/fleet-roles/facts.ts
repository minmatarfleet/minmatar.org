/**
 * Numbers the guide prose quotes, read from the SDE constants the simulators
 * use (sim_constants.json, written by scripts/extract_role_sim_constants.mjs).
 * Prose writes {key}; fill_facts swaps in the value, so a CCP balance change
 * reaches the text on the next extraction instead of waiting for an editor.
 */
import constants from './sim_constants.json'

type Constant = { value: number }

const values = constants.values as Record<string, Constant>

function format(value: number): string {
    return Number.isInteger(value) ? value.toLocaleString('en-US') : String(Number(value.toFixed(2)))
}

/** Every SDE constant by key, formatted for prose. */
export const sim_facts: Record<string, string> = Object.fromEntries(
    Object.entries(values).map(([key, constant]) => [key, format(constant.value)]),
)

// Prose-only aliases for constants that have a longer name in the JSON.
sim_facts.rr_optimal_km = sim_facts.large_rar_optimal_km
sim_facts.rr_falloff_km = sim_facts.large_rar_falloff_km

const TOKEN = /\{([a-z0-9_]+)\}/g

/** Fill {key} tokens. An unknown key is left as written, so a test can find it. */
export function fill_facts(text: string): string {
    return text.replace(TOKEN, (match, key: string) => sim_facts[key] ?? match)
}
