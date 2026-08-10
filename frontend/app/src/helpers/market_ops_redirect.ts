import type { Location } from '@dtypes/api.minmatar.org'

export const AMAMAKE_LOCATION_ID = 1022167642188
export const R_6KYM_2_LOCATION_ID = 1053229023468

/** Canonical market-ops page paths (no location query — single staging). */
export const OPS_PATHS = {
    monitor: '/market/ops/',
    contracts: '/market/ops/contracts/',
    sell_orders: '/market/ops/sell_orders/',
} as const

export type OpsPathKey = keyof typeof OPS_PATHS

/** Staging slug -> location_id when the slug appears in legacy query params. */
const STAGING_SLUG_LOCATION_IDS: Record<string, number> = {
    amamake: AMAMAKE_LOCATION_ID,
    r6_2: R_6KYM_2_LOCATION_ID,
}

/** Cover/legacy slug -> EveLocation.location_name */
const LOCATION_NAME_ALIASES: Record<string, string> = {
    amamake: 'Amamake - 5 times nearly AT winners',
    r6_2: 'R-6KYM - Casper Anchored It',
}

function normalize_key(value: string): string {
    return value.trim().toLowerCase()
}

function find_location_by_name_or_slug(
    locations: Location[],
    raw: string,
): Location | undefined {
    const normalized = normalize_key(raw)

    const slug_id = STAGING_SLUG_LOCATION_IDS[normalized]
    if (slug_id != null) {
        const by_slug = locations.find(loc => loc.location_id === slug_id)
        if (by_slug)
            return by_slug
    }

    const alias_name = LOCATION_NAME_ALIASES[normalized]
    if (alias_name) {
        const by_alias = locations.find(
            loc => normalize_key(loc.location_name) === normalize_key(alias_name),
        )
        if (by_alias)
            return by_alias
    }

    return locations.find(loc =>
        normalize_key(loc.location_name) === normalized
        || (loc.short_name && normalize_key(loc.short_name) === normalized),
    )
}

export function find_location_by_query(
    locations: Location[],
    searchParams: URLSearchParams,
): Location | undefined {
    const location_id_param = searchParams.get('location_id')
    if (location_id_param) {
        const parsed = parseInt(location_id_param, 10)
        if (!Number.isNaN(parsed)) {
            const by_id = locations.find(loc => loc.location_id === parsed)
            if (by_id)
                return by_id
        }
    }

    const location_name_param = searchParams.get('location_name')
    if (location_name_param)
        return find_location_by_name_or_slug(locations, location_name_param)

    return undefined
}

export function resolve_ops_location_id(
    locations: Location[],
    searchParams: URLSearchParams,
): number | undefined {
    return find_location_by_query(locations, searchParams)?.location_id
}

export function has_ops_deep_link_params(searchParams: URLSearchParams): boolean {
    return searchParams.has('location_id')
        || searchParams.has('location_name')
        || searchParams.has('doctrine_id')
        || searchParams.has('doctrine_name')
}

/**
 * Single staging for now: page URLs should not carry location/doctrine query
 * params. Canonicalize by stripping them.
 */
export function ops_params_need_canonicalization(
    searchParams: URLSearchParams,
    _resolved_location_id?: number,
): boolean {
    return has_ops_deep_link_params(searchParams)
}

export function ops_redirect_path(
    translatePath: (path: string) => string,
    page: OpsPathKey = 'monitor',
): string {
    return translatePath(OPS_PATHS[page])
}

/** Legacy /market deep links and /market/jobs → Market Ops monitor. */
export function ops_redirect_target(
    translatePath: (path: string) => string,
    _locations?: Location[],
    _searchParams?: URLSearchParams,
): string {
    return ops_redirect_path(translatePath, 'monitor')
}
