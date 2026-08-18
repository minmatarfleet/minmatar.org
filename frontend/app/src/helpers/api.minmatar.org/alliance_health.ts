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

export function alliance_health_table_params(opts: {
    bucket: string
    corp?: string
    can_mutate?: boolean
    alliance_wide?: boolean
    officer_corp_ids?: number[]
    can_leave_any?: boolean
    ceo_corp_ids?: number[]
}): string {
    return query_string({
        bucket: opts.bucket,
        corp: opts.corp ?? 'all',
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
