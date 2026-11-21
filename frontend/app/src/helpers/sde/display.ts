/**
 * How static EVE data is displayed: security status rounding and colours, and
 * meta group colours. Pure functions with no database access, so components,
 * partials and stories can all use them.
 */
import type { SecurityBand } from '@dtypes/sde'

const WORMHOLE_MIN_ID = 31000000
const WORMHOLE_MAX_ID = 31999999

/**
 * Security status as the EVE client shows it: rounded to one decimal, except
 * that a system between 0.0 and 0.05 shows 0.1 (it is low-sec, not null-sec).
 */
export function display_security(security: number): number {
    if (!Number.isFinite(security))
        return 0
    if (security > 0 && security < 0.05)
        return 0.1
    const rounded = Math.round(security * 10) / 10
    return rounded === 0 ? 0 : rounded
}

/** The displayed security as text: `0.4`, `-0.1`, `1.0`. Never `-0.0`. */
export function format_security(security: number): string {
    return display_security(security).toFixed(1)
}

export const is_wormhole_system = (system_id?: number | null): boolean =>
    typeof system_id === 'number' && system_id >= WORMHOLE_MIN_ID && system_id <= WORMHOLE_MAX_ID

/** High-sec (0.5 and up), low-sec (0.1 to 0.4), null-sec (0.0 and below), or J-space by system id. */
export function security_band(security: number, system_id?: number | null): SecurityBand {
    if (is_wormhole_system(system_id))
        return 'wormhole'
    const shown = display_security(security)
    if (shown >= 0.5)
        return 'high'
    if (shown > 0)
        return 'low'
    return 'null'
}

/** The colour token for a security status, without `--`: `security-status-point-4`. */
export function security_token(security: number): string {
    const shown = display_security(security)
    if (shown >= 1)
        return 'security-status-1'
    if (shown <= 0)
        return 'security-status-null'
    return `security-status-point-${Math.round(shown * 10)}`
}

const META_GROUP_TOKENS: Record<string, string> = {
    'Tech I':       'tech-i',
    'Tech II':      'tech-ii',
    'Tech III':     'tech-iii',
    'Storyline':    'storyline',
    'Faction':      'faction',
    'Officer':      'officer',
    'Deadspace':    'deadspace',
    'Abyssal':      'abyssal',
}

/** The colour token for a meta group name, without `--`, or null for groups without one (Premium, Structure...). */
export function meta_group_token(meta_group_name?: string | null): string | null {
    if (!meta_group_name)
        return null
    return META_GROUP_TOKENS[meta_group_name] ?? null
}

/** Tokens light enough that a filled tag needs dark text. */
export const LIGHT_META_TOKENS = ['tech-i']

/**
 * A same-site link template for result rows, or undefined when it is not one.
 * Only paths starting with a single `/` pass, so a partial's `href` query
 * parameter cannot point rows at another site.
 */
export function safe_href_template(template?: string | null): string | undefined {
    if (!template || !/^\/(?!\/)[^\s\\]*$/.test(template))
        return undefined
    return template
}

/** Fill `{name}` placeholders in a link template; values are URL-encoded. */
export function fill_href_template(template: string, values: Record<string, string | number>): string {
    return template.replace(/\{(\w+)\}/g, (match, key: string) =>
        key in values ? encodeURIComponent(String(values[key])) : match)
}
