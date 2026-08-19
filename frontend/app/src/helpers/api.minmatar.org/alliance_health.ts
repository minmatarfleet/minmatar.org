import { parse_response_error, query_string } from '@helpers/string'
import type {
    AllianceHealthAttention,
    AllianceHealthAttentionBucket,
    AllianceHealthCorporations,
    AllianceHealthLeave,
    AllianceHealthLeaveBucket,
    AllianceHealthOnboarding,
    AllianceHealthOnboardingBucket,
    AllianceHealthOverview,
    AllianceHealthTrialBucket,
    AllianceHealthTrials,
} from '@dtypes/api.minmatar.org'

const API_ENDPOINT = `${import.meta.env.API_URL}/api/alliance/health`

async function get_json<T>(access_token: string, path: string): Promise<T> {
    const headers = {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${access_token}`,
    }
    const ENDPOINT = `${API_ENDPOINT}${path}`
    const METHOD = 'GET'
    console.log(`Requesting ${METHOD}: ${ENDPOINT}`)
    try {
        const response = await fetch(ENDPOINT, {
            headers,
            method: METHOD,
        })
        if (!response.ok) {
            throw new Error(
                await parse_response_error(response, `${METHOD} ${ENDPOINT}`),
                { cause: response.status },
            )
        }
        return (await response.json()) as T
    } catch (error) {
        throw new Error(`Error fetching alliance health${path}: ${error.message}`, {
            cause: error.cause,
        })
    }
}

export async function get_alliance_health_overview(access_token: string) {
    return get_json<AllianceHealthOverview>(access_token, '/overview')
}

export async function get_alliance_health_attention(
    access_token: string,
    bucket: AllianceHealthAttentionBucket = 'fading',
) {
    const query = query_string({ bucket })
    return get_json<AllianceHealthAttention>(
        access_token,
        `/attention${query ? `?${query}` : ''}`,
    )
}

export async function get_alliance_health_trials(
    access_token: string,
    bucket: AllianceHealthTrialBucket = 'current',
) {
    const query = query_string({ bucket })
    return get_json<AllianceHealthTrials>(
        access_token,
        `/trials${query ? `?${query}` : ''}`,
    )
}

export async function get_alliance_health_leave(
    access_token: string,
    bucket: AllianceHealthLeaveBucket = 'current',
) {
    const query = query_string({ bucket })
    return get_json<AllianceHealthLeave>(
        access_token,
        `/leave${query ? `?${query}` : ''}`,
    )
}

export async function get_alliance_health_onboarding(
    access_token: string,
    bucket: AllianceHealthOnboardingBucket = 'first_week',
) {
    const query = query_string({ bucket })
    return get_json<AllianceHealthOnboarding>(
        access_token,
        `/onboarding${query ? `?${query}` : ''}`,
    )
}

export async function get_alliance_health_corporations(access_token: string) {
    return get_json<AllianceHealthCorporations>(access_token, '/corporations')
}

export async function post_alliance_health_status(
    access_token: string,
    user_id: number,
    action: 'promote' | 'leave' | 'restore',
    reason = '',
) {
    const headers = {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${access_token}`,
    }
    const ENDPOINT = `${API_ENDPOINT}/status`
    const response = await fetch(ENDPOINT, {
        headers,
        method: 'POST',
        body: JSON.stringify({ user_id, action, reason }),
    })
    if (!response.ok) {
        throw new Error(
            await parse_response_error(response, `POST ${ENDPOINT}`),
            { cause: response.status },
        )
    }
    return await response.json()
}

export function alliance_health_counts_for_corp<T extends Record<string, number>>(
    counts: T,
    counts_by_corp: Record<string, T> | undefined,
    corp: string,
): T {
    if (!corp || corp === 'all') {
        return counts_by_corp?.all ?? counts
    }
    if (counts_by_corp?.[corp]) return counts_by_corp[corp]
    const zero = { ...counts }
    for (const key of Object.keys(zero) as (keyof T)[]) {
        zero[key] = 0 as T[keyof T]
    }
    return zero
}

export function alliance_health_corp_options(
    counts_by_corp: Record<string, unknown> | undefined,
    extra: string[] = [],
): string[] {
    const names = new Set(
        [...Object.keys(counts_by_corp ?? {}), ...extra].filter(
            (name) => name && name !== 'all' && name !== '—',
        ),
    )
    return [...names].sort((a, b) => a.localeCompare(b))
}

export function alliance_health_table_params(opts: {
    bucket: string
    corp?: string
    include_corp?: boolean
    can_mutate?: boolean
    alliance_wide?: boolean
    officer_corp_ids?: number[]
    can_leave_any?: boolean
    ceo_corp_ids?: number[]
}): string {
    return query_string({
        bucket: opts.bucket,
        ...(opts.include_corp === false ? {} : { corp: opts.corp ?? 'all' }),
        can_mutate: opts.can_mutate ? '1' : '0',
        alliance_wide: opts.alliance_wide ? '1' : '0',
        officer_corps: (opts.officer_corp_ids ?? []).join(','),
        can_leave_any: opts.can_leave_any ? '1' : '0',
        ceo_corps: (opts.ceo_corp_ids ?? []).join(','),
    })
}

export function can_leave_alliance_health_pilot(
    corporation_id: number | null | undefined,
    can_leave_any: boolean,
    ceo_corp_ids: number[],
): boolean {
    if (can_leave_any) return true
    return (
        corporation_id != null && ceo_corp_ids.includes(corporation_id)
    )
}

export function can_act_on_alliance_health_corp(
    alliance_wide: boolean,
    corporation_id: number | null | undefined,
    officer_corp_ids: number[],
): boolean {
    if (alliance_wide) return true
    return (
        corporation_id != null && officer_corp_ids.includes(corporation_id)
    )
}

export function can_promote_alliance_health_trial(opts: {
    can_mutate: boolean
    bucket: AllianceHealthTrialBucket | string
    alliance_wide: boolean
    officer_corp_ids: number[]
    corporation_id?: number | null
    decision?: string | null
    alliance_days?: number | null
}): boolean {
    if (!opts.can_mutate) return false
    if (
        !can_act_on_alliance_health_corp(
            opts.alliance_wide,
            opts.corporation_id,
            opts.officer_corp_ids,
        )
    ) {
        return false
    }
    if (opts.decision === 'too_early') return false
    if (opts.decision === 'approve') return true
    const bucket = opts.bucket as AllianceHealthTrialBucket
    switch (bucket) {
        case 'approve':
        case 'remove':
            return true
        case 'passing':
            return (opts.alliance_days ?? 0) >= 60
        case 'current':
        case 'failing':
        case 'evaluating':
        case 'add':
        case 'flagged':
        case 'too_early':
        case 'fail':
        case 'nudge':
            return false
        default: {
            const _never: never = bucket
            return _never
        }
    }
}
