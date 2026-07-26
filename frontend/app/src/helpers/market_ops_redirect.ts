import type { Location } from '@dtypes/api.minmatar.org'
import { query_string } from '@helpers/string'

export const AMAMAKE_LOCATION_ID = 1022167642188
export const R_6KYM_2_LOCATION_ID = 1053229023468

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

export function ops_params_need_canonicalization(
    searchParams: URLSearchParams,
    resolved_location_id?: number,
): boolean {
    if (
        searchParams.has('location_name')
        || searchParams.has('doctrine_id')
        || searchParams.has('doctrine_name')
    ) {
        return true
    }

    const location_id_param = searchParams.get('location_id')
    if (!location_id_param)
        return resolved_location_id != null

    const parsed = parseInt(location_id_param, 10)
    if (Number.isNaN(parsed))
        return true

    return resolved_location_id != null && parsed !== resolved_location_id
}

export function ops_redirect_path(
    translatePath: (path: string) => string,
    location_id?: number,
): string {
    if (location_id != null)
        return translatePath(`/market/ops/?${query_string({ location_id })}`)

    return translatePath('/market/ops/')
}

export function ops_redirect_target(
    translatePath: (path: string) => string,
    locations: Location[],
    searchParams: URLSearchParams,
): string {
    const location_id = resolve_ops_location_id(locations, searchParams)
    return ops_redirect_path(translatePath, location_id)
}
