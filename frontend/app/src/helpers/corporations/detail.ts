import type { CorporationMemberDetails } from '@dtypes/api.minmatar.org'

// Keep in step with corporation_slug in backend/eveonline/helpers/corporations/slugs.py.
export function corporation_slug(name: string | null | undefined): string {
    return (name ?? '').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '')
}

// Readable name URL; falls back to the ID when a name has no ASCII letters or digits.
export function corporation_path(corporation_id: number, name?: string | null): string {
    return `/alliance/corporations/${corporation_slug(name) || corporation_id}/`
}

export type MemberSortMetric = 'fleets' | 'kills' | 'voice' | 'timezone'

export const MEMBER_PAGE_SIZE = 25

const OBSERVED_TZ_ORDER = ['US', 'US_AP', 'AP', 'AP_EU', 'EU', 'EU_US'] as const

export interface CorporationMemberPortrait {
    character_id: number
    character_name: string
}

export interface CorporationMemberAlt extends CorporationMemberPortrait {
    exempt: boolean
    esi_suspended: boolean
}

export interface CorporationMemberRow {
    character_id: number
    character_name: string
    user_name: string | null
    exempt: boolean
    esi_suspended: boolean
    alts: CorporationMemberAlt[]
    primary: CorporationMemberPortrait | null
    registered: boolean
    token_count: number
    fleets_90d: number
    kills_90d: number
    voice_hours_90d: number
    observed_prime_times: string[]
    prime_time: string | null
    community_status: string | null
    // Characters the viewer may not see; only their count is known.
    hidden_character_count: number
    // Belongs to a site account. Rows with hidden characters omit the
    // username, so they carry this flag instead.
    linked: boolean
}

export const MEMBER_TIMEZONE_FILTERS = OBSERVED_TZ_ORDER
export const MEMBER_STATUS_FILTERS = ['active', 'trial', 'on_leave', 'none'] as const
export type MemberStatusFilter = typeof MEMBER_STATUS_FILTERS[number]
// Linked = the character belongs to a site account; "not linked" are in-game
// members nobody has registered yet.
export const MEMBER_ACCOUNT_FILTERS = ['linked', 'unlinked', 'all'] as const
export type MemberAccountFilter = typeof MEMBER_ACCOUNT_FILTERS[number]

export interface MemberFilters {
    query: string
    registered_only?: boolean
    timezone?: string | null
    status?: string | null
    account?: MemberAccountFilter | null
}

export interface MemberTimezones {
    codes: string[]
    declared: boolean
}

// Where they actually fleet; fall back to the timezone they declared.
export function corporation_member_timezones(row: CorporationMemberRow): MemberTimezones {
    if (row.observed_prime_times.length > 0)
        return { codes: row.observed_prime_times, declared: false }
    if (row.prime_time)
        return { codes: [row.prime_time], declared: true }
    return { codes: [], declared: false }
}

export function member_filter_value<T extends string>(
    value: string | null,
    allowed: readonly T[],
): T | null {
    return value && (allowed as readonly string[]).includes(value) ? value as T : null
}

export function corporation_member_page(value: string | null): number {
    const parsed = Number.parseInt(value ?? '', 10)
    if (!Number.isFinite(parsed) || parsed < 1)
        return 1
    return parsed
}

function group_key(member: CorporationMemberDetails): string | null {
    if (member.primary_character_id)
        return `primary:${member.primary_character_id}`
    const user_name = member.user_name?.trim()
    if (user_name)
        return `user:${user_name}`
    return null
}

function by_activity(a: CorporationMemberDetails, b: CorporationMemberDetails): number {
    return b.fleets_90d - a.fleets_90d
        || b.kills_90d - a.kills_90d
        || a.character_name.localeCompare(b.character_name)
}

function observed_rank(times: string[]): number {
    for (const code of times) {
        const index = OBSERVED_TZ_ORDER.indexOf(code as typeof OBSERVED_TZ_ORDER[number])
        if (index >= 0)
            return index
    }
    return OBSERVED_TZ_ORDER.length
}

function unique_observed(members: CorporationMemberDetails[]): string[] {
    const present = new Set(members.flatMap((member) => member.observed_prime_times ?? []))
    const known = new Set<string>(OBSERVED_TZ_ORDER)
    const ordered = OBSERVED_TZ_ORDER.filter((code) => present.has(code))
    const extras = [...present].filter((code) => !known.has(code))
    return [...ordered, ...extras]
}

function sum_hours(values: number[]): number {
    const total = values.reduce((sum, value) => sum + value, 0)
    return Math.round(total * 10) / 10
}

function collapse_group(group: CorporationMemberDetails[]): CorporationMemberRow {
    const primary_id = group.find((member) => member.primary_character_id)?.primary_character_id ?? null
    const primary_name = group.find((member) => member.primary_character_name)?.primary_character_name ?? null
    const in_corp_primary = primary_id == null
        ? undefined
        : group.find((member) => member.character_id === primary_id)
    const main = in_corp_primary ?? [...group].sort(by_activity)[0]
    const alts = group
        .filter((member) => member.character_id !== main.character_id)
        .sort((a, b) => a.character_name.localeCompare(b.character_name))
        .map((member) => ({
            character_id: member.character_id,
            character_name: member.character_name,
            exempt: member.exempt,
            esi_suspended: member.esi_suspended,
        }))
    const primary_in_roster = primary_id != null && (
        primary_id === main.character_id
        || alts.some((alt) => alt.character_id === primary_id)
    )
    const primary = primary_id != null && primary_name && !primary_in_roster
        ? { character_id: primary_id, character_name: primary_name }
        : null
    return {
        character_id: main.character_id,
        character_name: main.character_name,
        user_name: group.find((member) => member.user_name)?.user_name ?? null,
        exempt: main.exempt,
        esi_suspended: main.esi_suspended,
        alts,
        primary,
        registered: group.some((member) => member.registered),
        token_count: group.reduce((sum, member) => sum + member.token_count, 0),
        fleets_90d: group.reduce((sum, member) => sum + member.fleets_90d, 0),
        kills_90d: group.reduce((sum, member) => sum + member.kills_90d, 0),
        voice_hours_90d: sum_hours(group.map((member) => member.voice_hours_90d)),
        observed_prime_times: unique_observed(group),
        prime_time: group.find((member) => member.prime_time)?.prime_time ?? null,
        community_status: group.find((member) => member.community_status)?.community_status ?? null,
        hidden_character_count: group.reduce((sum, member) => sum + (member.hidden_character_count ?? 0), 0),
        linked: group.some((member) => Boolean(member.user_name) || Boolean(member.characters_hidden)),
    }
}

export function corporation_member_primary(row: CorporationMemberRow): CorporationMemberPortrait {
    if (row.primary)
        return row.primary
    return {
        character_id: row.character_id,
        character_name: row.character_name,
    }
}

export function corporation_member_characters(row: CorporationMemberRow): CorporationMemberAlt[] {
    const primary_id = corporation_member_primary(row).character_id
    const characters: CorporationMemberAlt[] = []
    if (row.character_id !== primary_id) {
        characters.push({
            character_id: row.character_id,
            character_name: row.character_name,
            exempt: row.exempt,
            esi_suspended: row.esi_suspended,
        })
    }
    for (const alt of row.alts) {
        if (alt.character_id !== primary_id && alt.character_id !== row.character_id)
            characters.push(alt)
    }
    return characters.sort((a, b) => a.character_name.localeCompare(b.character_name))
}

export function group_corporation_members(
    members: CorporationMemberDetails[],
): CorporationMemberRow[] {
    const groups = new Map<string, CorporationMemberDetails[]>()
    const singles: CorporationMemberDetails[] = []
    for (const member of members) {
        const key = group_key(member)
        if (!key) {
            singles.push(member)
            continue
        }
        const group = groups.get(key) ?? []
        group.push(member)
        groups.set(key, group)
    }
    return [
        ...[...groups.values()].map(collapse_group),
        ...singles.map((member) => collapse_group([member])),
    ]
}

export function filter_corporation_member_rows(
    rows: CorporationMemberRow[],
    options: MemberFilters,
): CorporationMemberRow[] {
    const query = options.query.trim().toLowerCase()
    return rows.filter((row) => {
        if (options.registered_only && !row.registered)
            return false
        if (options.account === 'linked' && !row.linked)
            return false
        if (options.account === 'unlinked' && row.linked)
            return false
        if (options.timezone && !corporation_member_timezones(row).codes.includes(options.timezone))
            return false
        if (options.status === 'none' && row.community_status)
            return false
        if (options.status && options.status !== 'none' && row.community_status !== options.status)
            return false
        if (!query)
            return true
        const names = [
            row.character_name,
            row.primary?.character_name,
            ...row.alts.map((alt) => alt.character_name),
        ]
        return names.some((name) => name?.toLowerCase().includes(query))
    })
}

export function sort_corporation_member_rows(
    rows: CorporationMemberRow[],
    metric: MemberSortMetric,
): CorporationMemberRow[] {
    const sorted = [...rows]
    sorted.sort((a, b) => {
        const by_name = a.character_name.localeCompare(b.character_name)
        switch (metric) {
            case 'fleets':
                return b.fleets_90d - a.fleets_90d || b.kills_90d - a.kills_90d || by_name
            case 'kills':
                return b.kills_90d - a.kills_90d || b.fleets_90d - a.fleets_90d || by_name
            case 'voice':
                return b.voice_hours_90d - a.voice_hours_90d || b.fleets_90d - a.fleets_90d || by_name
            case 'timezone':
                return observed_rank(a.observed_prime_times) - observed_rank(b.observed_prime_times) || by_name
            default: {
                const unexpected: never = metric
                return unexpected
            }
        }
    })
    return sorted
}

export function paginate_corporation_member_rows<T>(
    items: T[],
    page: number,
    page_size = MEMBER_PAGE_SIZE,
) {
    const total = items.length
    const total_pages = Math.max(1, Math.ceil(total / page_size))
    const current = Math.min(Math.max(1, page), total_pages)
    const start = (current - 1) * page_size
    return {
        page: current,
        page_size,
        total,
        total_pages,
        rows: items.slice(start, start + page_size),
    }
}
