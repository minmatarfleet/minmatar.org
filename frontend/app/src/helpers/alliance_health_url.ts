export const ALLIANCE_HEALTH_URL_SECTIONS = [
    'onboarding',
    'trials',
    'leave',
    'attention',
    'corps',
] as const

export type AllianceHealthUrlSection =
    (typeof ALLIANCE_HEALTH_URL_SECTIONS)[number]

export const ALLIANCE_HEALTH_BUCKETS = {
    onboarding: ['first_week', 'more_fleets'],
    trials: [
        'current',
        'passing',
        'failing',
        'evaluating',
        'add',
        'remove',
        'flagged',
        'approve',
        'too_early',
        'fail',
        'nudge',
    ],
    leave: ['current', 'inactive', 'returning', 'add', 'remove', 'flagged'],
    attention: ['fading', 'dark', 'seasonal'],
} as const

export const ALLIANCE_HEALTH_DEFAULT_BUCKETS = {
    onboarding: 'first_week',
    trials: 'current',
    leave: 'current',
    attention: 'fading',
} as const

export type AllianceHealthUrlOrderDir = 'asc' | 'desc'

export interface AllianceHealthUrlListState {
    bucket?: string
    corp: string
    q: string
    by: string
    dir: AllianceHealthUrlOrderDir
    page: number
}

export interface AllianceHealthUrlListPatch {
    bucket?: string
    corp?: string
    q?: string
    by?: string
    dir?: AllianceHealthUrlOrderDir
    page?: number
}

export interface AllianceHealthUrlListDefaults {
    bucket?: string
    corp?: string
    by?: string
    dir?: AllianceHealthUrlOrderDir
    page?: number
}

export function alliance_health_section_hash(
    section: AllianceHealthUrlSection,
): string {
    return `health-${section}`
}

export function parse_alliance_health_bucket<
    S extends keyof typeof ALLIANCE_HEALTH_BUCKETS,
>(
    section: S,
    raw: string | null | undefined,
): (typeof ALLIANCE_HEALTH_BUCKETS)[S][number] {
    const allowed = ALLIANCE_HEALTH_BUCKETS[section] as readonly string[]
    const fallback = ALLIANCE_HEALTH_DEFAULT_BUCKETS[section]
    if (raw && allowed.includes(raw))
        return raw as (typeof ALLIANCE_HEALTH_BUCKETS)[S][number]
    return fallback
}

function keys_for(section: AllianceHealthUrlSection) {
    return {
        bucket: section,
        corp: `${section}_corp`,
        q: `${section}_q`,
        by: `${section}_by`,
        dir: `${section}_dir`,
        page: `${section}_p`,
    }
}

function parse_dir(raw: string | null): AllianceHealthUrlOrderDir | undefined {
    if (raw === 'asc' || raw === 'desc') return raw
    return undefined
}

function parse_page(raw: string | null): number | undefined {
    if (!raw) return undefined
    const page = Number.parseInt(raw, 10)
    if (!Number.isFinite(page) || page < 1) return undefined
    return page
}

export function read_alliance_health_list_state(
    params: URLSearchParams,
    section: AllianceHealthUrlSection,
    defaults: AllianceHealthUrlListDefaults,
): AllianceHealthUrlListState {
    const keys = keys_for(section)
    const fallback_corp = defaults.corp ?? 'all'
    const fallback_by = defaults.by ?? ''
    const fallback_dir = defaults.dir ?? 'desc'
    const fallback_page = defaults.page ?? 1
    const corp = params.get(keys.corp)?.trim() || fallback_corp
    const q = params.get(keys.q) ?? ''
    const by = params.get(keys.by)?.trim() || fallback_by
    const dir = parse_dir(params.get(keys.dir)) ?? fallback_dir
    const page = parse_page(params.get(keys.page)) ?? fallback_page
    const state: AllianceHealthUrlListState = {
        corp,
        q,
        by,
        dir,
        page,
    }
    if (section !== 'corps') {
        state.bucket = parse_alliance_health_bucket(
            section,
            params.get(keys.bucket),
        )
    }
    return state
}

export function patch_from_alliance_health_params(
    params: URLSearchParams,
    section: AllianceHealthUrlSection,
): AllianceHealthUrlListPatch {
    const keys = keys_for(section)
    const patch: AllianceHealthUrlListPatch = {}
    if (section !== 'corps' && params.has(keys.bucket)) {
        patch.bucket = parse_alliance_health_bucket(section, params.get(keys.bucket))
    }
    if (params.has(keys.corp)) patch.corp = params.get(keys.corp)?.trim() || 'all'
    if (params.has(keys.q)) patch.q = params.get(keys.q) ?? ''
    if (params.has(keys.by)) patch.by = params.get(keys.by)?.trim() || ''
    const dir = parse_dir(params.get(keys.dir))
    if (params.has(keys.dir) && dir) patch.dir = dir
    const page = parse_page(params.get(keys.page))
    if (page) patch.page = page
    return patch
}

function set_or_omit(
    params: URLSearchParams,
    key: string,
    value: string,
    omit: string,
) {
    if (!value || value === omit) params.delete(key)
    else params.set(key, value)
}

export function write_alliance_health_list_params(
    params: URLSearchParams,
    section: AllianceHealthUrlSection,
    patch: AllianceHealthUrlListPatch,
    defaults: AllianceHealthUrlListDefaults = {},
): void {
    const keys = keys_for(section)
    if (patch.bucket !== undefined && section !== 'corps') {
        set_or_omit(
            params,
            keys.bucket,
            patch.bucket,
            defaults.bucket ?? ALLIANCE_HEALTH_DEFAULT_BUCKETS[section],
        )
    }
    if (patch.corp !== undefined) {
        set_or_omit(params, keys.corp, patch.corp, defaults.corp ?? 'all')
    }
    if (patch.q !== undefined) {
        set_or_omit(params, keys.q, patch.q.trim(), '')
    }
    if (patch.by !== undefined || patch.dir !== undefined) {
        const by = patch.by ?? params.get(keys.by) ?? defaults.by ?? ''
        const dir =
            patch.dir ??
            parse_dir(params.get(keys.dir)) ??
            defaults.dir ??
            'desc'
        const by_default = defaults.by ?? ''
        const dir_default = defaults.dir ?? 'desc'
        if (by === by_default && dir === dir_default) {
            params.delete(keys.by)
            params.delete(keys.dir)
        } else {
            if (by) params.set(keys.by, by)
            else params.delete(keys.by)
            params.set(keys.dir, dir)
        }
    }
    if (patch.page !== undefined) {
        const page = Math.max(1, Math.trunc(patch.page) || 1)
        if (page === (defaults.page ?? 1)) params.delete(keys.page)
        else params.set(keys.page, String(page))
    }
}

export function alliance_health_href(
    pathname: string,
    params: URLSearchParams,
    hash = '',
): string {
    const search = params.toString()
    const hash_part = hash && !hash.startsWith('#') ? `#${hash}` : hash
    return `${pathname}${search ? `?${search}` : ''}${hash_part}`
}
