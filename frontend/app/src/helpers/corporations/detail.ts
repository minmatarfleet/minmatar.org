import type { CorporationMemberDetails, TimezoneTag } from '@dtypes/api.minmatar.org'
import { TIMEZONE_FILTERS, timezone_matches, timezone_rank } from '@helpers/timezones'

// Keep in step with corporation_slug in backend/eveonline/helpers/corporations/slugs.py.
export function corporation_slug(name: string | null | undefined): string {
    return (name ?? '').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '')
}

// Readable name URL; falls back to the ID when a name has no ASCII letters or digits.
export function corporation_path(corporation_id: number, name?: string | null): string {
    return `/alliance/corporations/${corporation_slug(name) || corporation_id}/`
}

// The detail page header's apply control; other Apply buttons on the page point here.
export const CORPORATION_APPLY_ID = 'corporation-apply'

export type MemberSortMetric = 'fleets' | 'kills' | 'voice' | 'timezone' | 'name' | 'joined' | 'last'
export const MEMBER_SORTS = ['fleets', 'kills', 'name', 'joined', 'last'] as const

export const MEMBER_PAGE_SIZE = 25

export interface CorporationMemberPortrait {
    character_id: number
    character_name: string
}

export interface CorporationMemberAlt extends CorporationMemberPortrait {
    exempt: boolean
    esi_suspended: boolean
    registered?: boolean
    token_level?: string
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
    // The person's timezone tag (alts share one account, so one tag).
    timezone: TimezoneTag | null
    community_status: string | null
    // Characters the viewer may not see; only their count is known.
    hidden_character_count: number
    // Belongs to a site account. Rows with hidden characters omit the
    // username, so they carry this flag instead.
    linked: boolean
    token_level: string
    // The main character itself has an ESI token (registered covers any character).
    main_registered: boolean
    corp_joined_at: string | null
    last_fleet_at: string | null
    weekly_fleets: number[]
    top_hull_id: number | null
    top_hull_name: string | null
    tribe_groups: string[]
    status_history: { to_status: string, changed_at: string }[]
    trial_ready: boolean
    trial_reason: string | null
}

// Who to look at (views) and what needs doing (attention). Views and
// attention filters are one choice: picking one replaces the other.
export const MEMBER_VIEWS = ['all', 'flying', 'quiet', 'new'] as const
export const MEMBER_ATTENTION_VIEWS = ['ready', 'unlinked', 'esi'] as const
export type MemberView = typeof MEMBER_VIEWS[number] | typeof MEMBER_ATTENTION_VIEWS[number]
export const FLYING_MIN_FLEETS = 3
export const NEW_MEMBER_DAYS = 90

export type MemberAttention = 'esi_suspended' | 'no_account' | 'token_missing' | 'trial_ready'

export const MEMBER_TIMEZONE_FILTERS = TIMEZONE_FILTERS
export const MEMBER_STATUS_FILTERS = ['active', 'trial', 'on_leave', 'none'] as const
export type MemberStatusFilter = typeof MEMBER_STATUS_FILTERS[number]
// Linked = the character belongs to a site account; "not linked" are in-game
// members nobody has registered yet.
export const MEMBER_ACCOUNT_FILTERS = ['linked', 'unlinked', 'all'] as const
export type MemberAccountFilter = typeof MEMBER_ACCOUNT_FILTERS[number]

export interface MemberFilters {
    query: string
    view?: MemberView | null
    registered_only?: boolean
    timezone?: typeof MEMBER_TIMEZONE_FILTERS[number] | null
    status?: string | null
    account?: MemberAccountFilter | null
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

function person_timezone(group: CorporationMemberDetails[]): TimezoneTag | null {
    return group.find((member) => member.timezone?.brackets?.length)?.timezone
        ?? group.find((member) => member.timezone)?.timezone
        ?? null
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
            registered: member.registered,
            token_level: member.token_level,
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
        // The API counts each fleet once per person; older payloads only per character.
        fleets_90d: person_fleets(group) ?? group.reduce((sum, member) => sum + member.fleets_90d, 0),
        kills_90d: group.reduce((sum, member) => sum + member.kills_90d, 0),
        voice_hours_90d: sum_hours(group.map((member) => member.voice_hours_90d)),
        timezone: person_timezone(group),
        community_status: group.find((member) => member.community_status)?.community_status ?? null,
        hidden_character_count: group.reduce((sum, member) => sum + (member.hidden_character_count ?? 0), 0),
        linked: group.some((member) => Boolean(member.user_name) || Boolean(member.characters_hidden)),
        token_level: main.token_level ?? '',
        main_registered: main.registered,
        corp_joined_at: earliest(group.map((member) => member.corp_joined_at)),
        last_fleet_at: latest(group.map((member) => member.last_fleet_at)),
        weekly_fleets: group.find((member) => member.weekly_fleets?.length)?.weekly_fleets ?? [],
        top_hull_id: main.top_hull_id ?? group.find((member) => member.top_hull_id)?.top_hull_id ?? null,
        top_hull_name: main.top_hull_name ?? group.find((member) => member.top_hull_name)?.top_hull_name ?? null,
        tribe_groups: group.find((member) => member.tribe_groups?.length)?.tribe_groups ?? [],
        status_history: group.find((member) => member.status_history?.length)?.status_history ?? [],
        trial_ready: group.some((member) => Boolean(member.trial_ready)),
        trial_reason: group.find((member) => member.trial_reason)?.trial_reason ?? null,
    }
}

function earliest(values: (string | null | undefined)[]): string | null {
    const present = values.filter((value): value is string => Boolean(value)).sort()
    return present[0] ?? null
}

function latest(values: (string | null | undefined)[]): string | null {
    const present = values.filter((value): value is string => Boolean(value)).sort()
    return present.at(-1) ?? null
}

function person_fleets(group: CorporationMemberDetails[]): number | null {
    const values = group
        .map((member) => member.person_fleets_90d)
        .filter((value): value is number => typeof value === 'number')
    return values.length > 0 ? Math.max(...values) : null
}

// A linked person with a character the site holds no ESI token for.
export function corporation_member_token_missing(row: CorporationMemberRow): boolean {
    if (!row.linked || row.hidden_character_count > 0)
        return false
    return !row.main_registered || row.alts.some((alt) => alt.registered === false)
}

// The one thing to flag on a row, most urgent first.
export function corporation_member_attention(row: CorporationMemberRow): MemberAttention | null {
    if (row.esi_suspended || row.alts.some((alt) => alt.esi_suspended))
        return 'esi_suspended'
    if (!row.linked)
        return 'no_account'
    if (corporation_member_token_missing(row))
        return 'token_missing'
    if (row.trial_ready)
        return 'trial_ready'
    return null
}

export function corporation_member_in_view(
    row: CorporationMemberRow,
    view: MemberView,
    now: Date = new Date(),
): boolean {
    switch (view) {
        case 'all':
            return row.linked
        case 'flying':
            return row.linked && row.fleets_90d >= FLYING_MIN_FLEETS
        case 'quiet':
            return row.linked && row.fleets_90d === 0
        case 'new': {
            const days = days_since(row.corp_joined_at, now)
            return row.linked && days !== null && days <= NEW_MEMBER_DAYS
        }
        case 'ready':
            return row.trial_ready
        case 'unlinked':
            return !row.linked
        case 'esi':
            return row.esi_suspended || row.alts.some((alt) => alt.esi_suspended)
                || corporation_member_token_missing(row)
        default: {
            const unexpected: never = view
            return unexpected
        }
    }
}

export function days_since(iso: string | null | undefined, now: Date = new Date()): number | null {
    if (!iso)
        return null
    const then = new Date(iso).getTime()
    if (Number.isNaN(then))
        return null
    return Math.max(0, Math.floor((now.getTime() - then) / 86_400_000))
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
        if (options.view && !corporation_member_in_view(row, options.view))
            return false
        if (options.registered_only && !row.registered)
            return false
        if (options.account === 'linked' && !row.linked)
            return false
        if (options.account === 'unlinked' && row.linked)
            return false
        if (options.timezone && !timezone_matches(row.timezone, options.timezone))
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
                return timezone_rank(a.timezone) - timezone_rank(b.timezone) || by_name
            case 'name':
                return by_name
            case 'joined':
                return (a.corp_joined_at ?? '9999').localeCompare(b.corp_joined_at ?? '9999') || by_name
            case 'last':
                return (b.last_fleet_at ?? '').localeCompare(a.last_fleet_at ?? '') || by_name
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

export interface MemberRosterParams extends MemberFilters {
    view: MemberView
    sort: typeof MEMBER_SORTS[number]
    page: number
    // Export only these characters (row character ids), when set.
    ids: number[]
}

// One parser for the table partial and the CSV export, so both filter alike.
export function parse_member_params(params: URLSearchParams): MemberRosterParams {
    const views = [...MEMBER_VIEWS, ...MEMBER_ATTENTION_VIEWS] as const
    return {
        query: (params.get('q') ?? '').trim().slice(0, 80),
        timezone: member_filter_value(params.get('tz'), MEMBER_TIMEZONE_FILTERS),
        status: member_filter_value(params.get('status'), MEMBER_STATUS_FILTERS),
        view: member_filter_value(params.get('view'), views) ?? 'all',
        sort: member_filter_value(params.get('sort'), MEMBER_SORTS) ?? 'fleets',
        page: corporation_member_page(params.get('page')),
        ids: (params.get('ids') ?? '')
            .split(',')
            .map((value) => Number.parseInt(value, 10))
            .filter((value) => Number.isFinite(value) && value > 0),
    }
}

export function build_member_roster(
    rows: CorporationMemberRow[],
    params: MemberRosterParams,
): CorporationMemberRow[] {
    const filtered = filter_corporation_member_rows(rows, params)
    const picked = params.ids.length > 0
        ? filtered.filter((row) => params.ids.includes(row.character_id))
        : filtered
    return sort_corporation_member_rows(picked, params.sort)
}

// Spreadsheet readers get words, not codes.
const ATTENTION_CSV_LABELS: Record<string, string> = {
    esi_suspended: 'ESI suspended',
    no_account: 'No site account',
    token_missing: 'No ESI token',
    trial_ready: 'Trial bar met',
}

function csv_cell(value: string | number | null | undefined): string {
    const text = value == null ? '' : String(value)
    return /[",\n\r]/.test(text) ? `"${text.replaceAll('"', '""')}"` : text
}

export function corporation_members_csv(rows: CorporationMemberRow[]): string {
    const header = [
        'Pilot', 'Alts', 'Status', 'In corp since', 'Fleets (90d)', 'Kills (90d)',
        'Voice hours (90d)', 'Last fleet', 'Timezone', 'Attention', 'Linked',
    ]
    const lines = rows.map((row) => {
        const primary = corporation_member_primary(row)
        const alts = row.hidden_character_count > 0
            ? String(row.hidden_character_count)
            : corporation_member_characters(row).map((alt) => alt.character_name).join('; ')
        return [
            primary.character_name,
            alts,
            row.community_status ?? '',
            row.corp_joined_at?.slice(0, 10) ?? '',
            row.fleets_90d,
            row.kills_90d,
            row.linked ? row.voice_hours_90d : '',
            row.last_fleet_at?.slice(0, 10) ?? '',
            (row.timezone?.brackets ?? []).join(' '),
            ATTENTION_CSV_LABELS[corporation_member_attention(row) ?? ''] ?? '',
            row.linked ? 'yes' : 'no',
        ].map(csv_cell).join(',')
    })
    return [header.join(','), ...lines].join('\n') + '\n'
}
