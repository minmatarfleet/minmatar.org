import type {
    CampaignListItem,
    CampaignDetail,
    CampaignRightNow,
    CampaignWeek,
    CampaignOrder,
    CampaignSystemSummary,
    CampaignLeaderboardRow,
    CampaignLeaderboardMetric,
    CampaignLeaderboardPeriod,
    CampaignKillmail,
    CampaignKillmailOutcome,
    CampaignSite,
    CampaignTimelineEvent,
    CampaignRoster,
    CampaignReadiness,
    CampaignEnlistRequest,
    CampaignEnlistResponse,
    CampaignAdvantageRequest,
    CampaignAdvantageResponse,
    CampaignGangRequest,
} from '@dtypes/api.minmatar.org'
import { parse_response_error } from '@helpers/string'

const API_ENDPOINT = `${import.meta.env.API_URL}/api/campaigns`

const build_headers = (access_token?:string | false) => {
    const headers = {
        'Content-Type': 'application/json',
    }

    if (access_token)
        headers['Authorization'] = `Bearer ${access_token}`

    return headers
}

async function request_json<Type>(
    endpoint:string,
    access_token:string | false,
    subject:string,
    method:string = 'GET',
    body?:unknown,
) {
    console.log(`Requesting: ${method} ${endpoint}`)

    try {
        const response = await fetch(endpoint, {
            method: method,
            headers: build_headers(access_token),
            ...(body !== undefined && { body: JSON.stringify(body) }),
        })

        if (!response.ok) {
            throw new Error(await parse_response_error(response, `${method} ${endpoint}`), {
                cause: response.status
            });
        }

        if (response.status === 204)
            return null as Type

        const text = await response.text()

        return (text ? JSON.parse(text) : null) as Type;
    } catch (error) {
        throw new Error(`Error fetching ${subject}: ${error.message}`, { cause: error.cause });
    }
}

export async function get_campaigns(access_token:string | false = false, status:string = '') {
    const params = status ? `?status=${encodeURIComponent(status)}` : ''

    return await request_json<CampaignListItem[]>(
        `${API_ENDPOINT}${params}`,
        access_token,
        'campaigns',
    )
}

export async function get_campaign(slug:string, access_token:string | false = false) {
    return await request_json<CampaignDetail>(
        `${API_ENDPOINT}/${slug}`,
        access_token,
        'campaign',
    )
}

export async function get_campaign_now(slug:string, access_token:string | false = false) {
    return await request_json<CampaignRightNow>(
        `${API_ENDPOINT}/${slug}/now`,
        access_token,
        'campaign live status',
    )
}

export async function get_campaign_week(slug:string, access_token:string | false = false) {
    return await request_json<CampaignWeek>(
        `${API_ENDPOINT}/${slug}/week`,
        access_token,
        'campaign week plan',
    )
}

export async function get_campaign_orders(slug:string, access_token:string | false = false) {
    return await request_json<CampaignOrder[]>(
        `${API_ENDPOINT}/${slug}/orders`,
        access_token,
        'campaign orders',
    )
}

export async function get_campaign_systems(slug:string, access_token:string | false = false) {
    return await request_json<CampaignSystemSummary[]>(
        `${API_ENDPOINT}/${slug}/systems`,
        access_token,
        'campaign systems',
    )
}

export async function get_campaign_leaderboard(
    slug:string,
    access_token:string | false = false,
    metric:CampaignLeaderboardMetric = 'points',
    period:CampaignLeaderboardPeriod = 'week',
    limit:number = 25,
) {
    const params = new URLSearchParams({
        metric: metric,
        period: period,
        limit: String(limit),
    })

    return await request_json<CampaignLeaderboardRow[]>(
        `${API_ENDPOINT}/${slug}/leaderboard?${params.toString()}`,
        access_token,
        'campaign leaderboard',
    )
}

export async function get_campaign_killmails(
    slug:string,
    access_token:string | false = false,
    outcome:CampaignKillmailOutcome | '' = '',
    limit:number = 25,
) {
    const params = new URLSearchParams({ limit: String(limit) })
    if (outcome) params.set('outcome', outcome)

    return await request_json<CampaignKillmail[]>(
        `${API_ENDPOINT}/${slug}/killmails?${params.toString()}`,
        access_token,
        'campaign killmails',
    )
}

export async function get_campaign_sites(slug:string, access_token:string | false = false, limit:number = 25) {
    return await request_json<CampaignSite[]>(
        `${API_ENDPOINT}/${slug}/sites?limit=${limit}`,
        access_token,
        'campaign sites',
    )
}

export async function get_campaign_timeline(slug:string, access_token:string | false = false, limit:number = 25) {
    return await request_json<CampaignTimelineEvent[]>(
        `${API_ENDPOINT}/${slug}/timeline?limit=${limit}`,
        access_token,
        'campaign timeline',
    )
}

export async function get_campaign_roster(slug:string, access_token:string | false = false) {
    return await request_json<CampaignRoster>(
        `${API_ENDPOINT}/${slug}/roster`,
        access_token,
        'campaign roster',
    )
}

export async function get_campaign_readiness(access_token:string) {
    return await request_json<CampaignReadiness>(
        `${API_ENDPOINT}/readiness`,
        access_token,
        'campaign character readiness',
    )
}

export async function enlist_campaign(slug:string, access_token:string, options:CampaignEnlistRequest = {}) {
    const body:CampaignEnlistRequest = {
        source: 'web',
        notify_gang_forming: true,
        notify_standing_fleet: true,
        notify_activity_nearby: false,
        notify_streak_at_risk: true,
        digest_hour: 18,
        ...options,
    }

    return await request_json<CampaignEnlistResponse>(
        `${API_ENDPOINT}/${slug}/enlist`,
        access_token,
        'campaign enlistment',
        'POST',
        body,
    )
}

export async function leave_campaign(slug:string, access_token:string) {
    return await request_json<CampaignEnlistResponse>(
        `${API_ENDPOINT}/${slug}/enlist`,
        access_token,
        'campaign enlistment',
        'DELETE',
    )
}

export async function include_campaign_character(slug:string, access_token:string, character_id:number) {
    return await request_json<unknown>(
        `${API_ENDPOINT}/${slug}/characters/${character_id}`,
        access_token,
        'campaign character',
        'PUT',
    )
}

export async function exclude_campaign_character(slug:string, access_token:string, character_id:number) {
    return await request_json<unknown>(
        `${API_ENDPOINT}/${slug}/characters/${character_id}`,
        access_token,
        'campaign character',
        'DELETE',
    )
}

export async function report_campaign_advantage(
    slug:string,
    access_token:string,
    system_id:number,
    reading:CampaignAdvantageRequest,
) {
    return await request_json<CampaignAdvantageResponse>(
        `${API_ENDPOINT}/${slug}/systems/${system_id}/advantage`,
        access_token,
        'campaign advantage reading',
        'POST',
        reading,
    )
}

export async function take_campaign_standing_fleet(slug:string, access_token:string) {
    return await request_json<unknown>(
        `${API_ENDPOINT}/${slug}/standing-fleet/take`,
        access_token,
        'campaign standing fleet',
        'POST',
        {},
    )
}

export async function join_campaign_standing_fleet(slug:string, access_token:string) {
    return await request_json<unknown>(
        `${API_ENDPOINT}/${slug}/standing-fleet/join`,
        access_token,
        'campaign standing fleet',
        'POST',
        {},
    )
}

export async function create_campaign_gang(slug:string, access_token:string, gang:CampaignGangRequest) {
    return await request_json<unknown>(
        `${API_ENDPOINT}/${slug}/gangs`,
        access_token,
        'campaign gang',
        'POST',
        gang,
    )
}
