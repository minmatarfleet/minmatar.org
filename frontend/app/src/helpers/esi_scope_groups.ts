import {
    BASIC_SCOPES,
    DESKTOP_SCOPES,
    DIRECTOR_SCOPES,
    FACTION_WARFARE_SCOPES,
    FLEET_COMMANDER_SCOPES,
    INDUSTRY_SCOPES,
    MARKET_SCOPES,
} from '@helpers/esi_token_scopes'

/** Groups offered in the add-character dialog. Mirrors backend SELECTABLE_SCOPE_GROUPS plus Basic. */
export type ScopeGroupKey = 'Basic' | 'FactionWarfare' | 'Industry' | 'Market' | 'Desktop' | 'FleetCommander' | 'Director'

export interface ScopeGroupOption {
    key:            ScopeGroupKey;
    /** Scopes this group adds on top of Basic (Basic lists its own). */
    scopes:         readonly string[];
    locked:         boolean;
    default_on:     boolean;
    role_specific:  boolean;
    /** Cookie version that first offered this group. Older cookies never answered for it, so it starts at its default. */
    since:          number;
}

export const SCOPE_GROUP_OPTIONS: readonly ScopeGroupOption[] = [
    { key: 'Basic',          scopes: BASIC_SCOPES,           locked: true,  default_on: true,  role_specific: false, since: 1 },
    { key: 'FactionWarfare', scopes: FACTION_WARFARE_SCOPES, locked: true,  default_on: true,  role_specific: false, since: 1 },
    { key: 'Industry',       scopes: INDUSTRY_SCOPES,        locked: false, default_on: true,  role_specific: false, since: 1 },
    { key: 'Market',         scopes: MARKET_SCOPES,          locked: false, default_on: true,  role_specific: false, since: 1 },
    { key: 'Desktop',        scopes: DESKTOP_SCOPES,         locked: false, default_on: true,  role_specific: false, since: 2 },
    { key: 'FleetCommander', scopes: FLEET_COMMANDER_SCOPES, locked: false, default_on: false, role_specific: true,  since: 1 },
    { key: 'Director',       scopes: DIRECTOR_SCOPES,        locked: false, default_on: false, role_specific: true,  since: 1 },
]

/** Remembers the optional groups picked last time, so the next alt starts from them. */
export const SCOPE_GROUPS_COOKIE = 'add_character_scope_groups'
export const SCOPE_GROUPS_COOKIE_MAX_AGE = 60 * 60 * 24 * 365
/** Stored when every optional group is off, so it is not mistaken for "never chosen". */
export const SCOPE_GROUPS_COOKIE_NONE = '-'
/**
 * Bumped when a new optional group is added. The cookie is written as `v2:Industry,Market`;
 * a cookie from before (no prefix is version 1) has no answer for newer groups, so those
 * start at their default instead of reading as switched off.
 */
export const SCOPE_GROUPS_COOKIE_VERSION = 2

const OPTIONAL_KEYS = SCOPE_GROUP_OPTIONS.filter(group => !group.locked).map(group => group.key)

/** Optional groups switched on: the cookie's answer for each group it has seen, else the default. */
export function chosen_scope_groups(cookie_value: string | null | undefined): ScopeGroupKey[] {
    const optional = SCOPE_GROUP_OPTIONS.filter(group => !group.locked)
    if (cookie_value === null || cookie_value === undefined || cookie_value === '')
        return optional.filter(group => group.default_on).map(group => group.key)

    const match = /^v(\d+):(.*)$/.exec(cookie_value)
    const version = match ? Number(match[1]) : 1
    const names = new Set((match ? match[2] : cookie_value).split(',').map(name => name.trim()))
    return optional
        .filter(group => group.since > version ? group.default_on : names.has(group.key))
        .map(group => group.key)
}

/** Cookie value for a set of optional groups. */
export function scope_groups_cookie_value(chosen: readonly string[]): string {
    const keys = OPTIONAL_KEYS.filter(key => chosen.includes(key))
    return `v${SCOPE_GROUPS_COOKIE_VERSION}:${keys.length ? keys.join(',') : SCOPE_GROUPS_COOKIE_NONE}`
}

/** Groups to send to the add endpoint: the required ones past Basic, then the chosen ones. */
export function requested_scope_groups(chosen: readonly string[]): ScopeGroupKey[] {
    return SCOPE_GROUP_OPTIONS
        .filter(group => group.key !== 'Basic' && (group.locked || chosen.includes(group.key)))
        .map(group => group.key)
}

/** `&scope_groups=...` for the add endpoint. */
export function scope_groups_query(chosen: readonly string[]): string {
    return `&scope_groups=${encodeURIComponent(requested_scope_groups(chosen).join(','))}`
}

/** How many distinct scopes Basic, the required groups and the chosen ones add up to. */
export function requested_scope_count(chosen: readonly string[]): number {
    const scopes = new Set<string>(BASIC_SCOPES)
    for (const key of requested_scope_groups(chosen)) {
        const group = SCOPE_GROUP_OPTIONS.find(option => option.key === key)
        group?.scopes.forEach(scope => scopes.add(scope))
    }
    return scopes.size
}
