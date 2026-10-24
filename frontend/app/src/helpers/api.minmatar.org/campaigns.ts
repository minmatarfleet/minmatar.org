import type {
    CampaignListItem,
    CampaignDetail,
    CampaignWeek,
    CampaignSystemSummary,
    CampaignFleet,
    CampaignLeaderboardRow,
    CampaignCorporationLeaderboardRow,
    CampaignLeaderboardMetric,
    CampaignLeaderboardPeriod,
    CampaignKillmail,
    CampaignKillmailOutcome,
    CampaignSite,
    CampaignRoster,
    CampaignReadiness,
    CampaignEnlistRequest,
    CampaignEnlistResponse,
    CampaignAdvantageRequest,
    CampaignAdvantageResponse,
    CampaignStructure,
    CampaignStructureAttachRequest,
    UniverseEntityMatch,
    CorporationProject,
} from '@dtypes/api.minmatar.org'
import { api_request } from '@helpers/api.minmatar.org/client'

const API_ENDPOINT = `${import.meta.env.API_URL}/api/campaigns`

export async function get_campaigns(access_token:string | false = false, status:string = '') {
    const params = status ? `?status=${encodeURIComponent(status)}` : ''

    return await api_request<CampaignListItem[]>(`${API_ENDPOINT}${params}`, {
        token: access_token,
        error: 'Error fetching campaigns',
    })
}

export async function get_campaign(slug:string, access_token:string | false = false) {
    return await api_request<CampaignDetail>(`${API_ENDPOINT}/${slug}`, {
        token: access_token,
        error: 'Error fetching campaign',
    })
}

export async function get_campaign_week(slug:string, access_token:string | false = false) {
    return await api_request<CampaignWeek>(`${API_ENDPOINT}/${slug}/week`, {
        token: access_token,
        error: 'Error fetching campaign week plan',
    })
}

export async function get_campaign_systems(slug:string, access_token:string | false = false) {
    return await api_request<CampaignSystemSummary[]>(`${API_ENDPOINT}/${slug}/systems`, {
        token: access_token,
        error: 'Error fetching campaign systems',
    })
}

export async function get_campaign_leaderboard(
    slug:string,
    access_token:string | false = false,
    metric:CampaignLeaderboardMetric = 'kills',
    period:CampaignLeaderboardPeriod = 'week',
    limit:number = 25,
) {
    const params = new URLSearchParams({
        metric: metric,
        period: period,
        limit: String(limit),
    })

    return await api_request<CampaignLeaderboardRow[]>(`${API_ENDPOINT}/${slug}/leaderboard?${params.toString()}`, {
        token: access_token,
        error: 'Error fetching campaign leaderboard',
    })
}

export async function get_campaign_corporation_leaderboard(
    slug:string,
    access_token:string | false = false,
    metric:CampaignLeaderboardMetric = 'kills',
    period:CampaignLeaderboardPeriod = 'week',
    limit:number = 25,
) {
    const params = new URLSearchParams({
        metric: metric,
        period: period,
        limit: String(limit),
    })

    return await api_request<CampaignCorporationLeaderboardRow[]>(`${API_ENDPOINT}/${slug}/leaderboard/corporations?${params.toString()}`, {
        token: access_token,
        error: 'Error fetching campaign corporation leaderboard',
    })
}

export async function get_campaign_killmails(
    slug:string,
    access_token:string | false = false,
    outcome:CampaignKillmailOutcome | '' = '',
    limit:number = 25,
    offset:number = 0,
) {
    const params = new URLSearchParams({ limit: String(limit) })
    if (outcome) params.set('outcome', outcome)
    if (offset > 0) params.set('offset', String(offset))

    return await api_request<CampaignKillmail[]>(`${API_ENDPOINT}/${slug}/killmails?${params.toString()}`, {
        token: access_token,
        error: 'Error fetching campaign killmails',
    })
}

export async function get_campaign_sites(slug:string, access_token:string | false = false, limit:number = 25, offset:number = 0) {
    return await api_request<CampaignSite[]>(`${API_ENDPOINT}/${slug}/sites?limit=${limit}${offset > 0 ? `&offset=${offset}` : ''}`, {
        token: access_token,
        error: 'Error fetching campaign sites',
    })
}

export async function get_campaign_fleets(slug:string, access_token:string | false = false, limit:number = 25) {
    return await api_request<CampaignFleet[]>(`${API_ENDPOINT}/${slug}/fleets?limit=${limit}`, {
        token: access_token,
        error: 'Error fetching campaign fleets',
    })
}

export async function get_campaign_roster(slug:string, access_token:string | false = false) {
    return await api_request<CampaignRoster>(`${API_ENDPOINT}/${slug}/roster`, {
        token: access_token,
        error: 'Error fetching campaign roster',
    })
}

export async function get_campaign_readiness(access_token:string) {
    return await api_request<CampaignReadiness>(`${API_ENDPOINT}/readiness`, {
        token: access_token,
        error: 'Error fetching campaign character readiness',
    })
}

export async function enlist_campaign(slug:string, access_token:string, options:CampaignEnlistRequest = {}) {
    const body:CampaignEnlistRequest = {
        source: 'web',
        notify_gang_forming: true,
        notify_standing_fleet: true,
        notify_activity_nearby: false,
        digest_hour: 18,
        ...options,
    }

    return await api_request<CampaignEnlistResponse>(`${API_ENDPOINT}/${slug}/enlist`, {
        method: 'POST',
        token: access_token,
        body: body,
        error: 'Error fetching campaign enlistment',
    })
}

export async function leave_campaign(slug:string, access_token:string) {
    return await api_request<CampaignEnlistResponse>(`${API_ENDPOINT}/${slug}/enlist`, {
        method: 'DELETE',
        token: access_token,
        error: 'Error fetching campaign enlistment',
    })
}

export async function include_campaign_character(slug:string, access_token:string, character_id:number) {
    return await api_request<unknown>(`${API_ENDPOINT}/${slug}/characters/${character_id}`, {
        method: 'PUT',
        token: access_token,
        error: 'Error fetching campaign character',
    })
}

export async function exclude_campaign_character(slug:string, access_token:string, character_id:number) {
    return await api_request<unknown>(`${API_ENDPOINT}/${slug}/characters/${character_id}`, {
        method: 'DELETE',
        token: access_token,
        error: 'Error fetching campaign character',
    })
}

export async function report_campaign_advantage(
    slug:string,
    access_token:string,
    system_id:number,
    reading:CampaignAdvantageRequest,
) {
    return await api_request<CampaignAdvantageResponse>(`${API_ENDPOINT}/${slug}/systems/${system_id}/advantage`, {
        method: 'POST',
        token: access_token,
        body: reading,
        error: 'Error fetching campaign advantage reading',
    })
}

export async function search_campaign_entities(
    access_token:string,
    kind:'corporation' | 'alliance',
    query:string,
) {
    const params = new URLSearchParams({ kind, q: query })
    return await api_request<UniverseEntityMatch[]>(`${API_ENDPOINT}/entities?${params}`, {
        token: access_token,
        error: 'Error fetching entity search',
    })
}

export async function attach_campaign_structure(
    slug:string,
    access_token:string,
    structure:CampaignStructureAttachRequest,
) {
    return await api_request<CampaignStructure>(`${API_ENDPOINT}/${slug}/structures`, {
        method: 'POST',
        token: access_token,
        body: structure,
        error: 'Error fetching campaign structure',
    })
}

export async function get_campaign_projects(slug:string, access_token:string | false = false) {
    return await api_request<CorporationProject[]>(`${API_ENDPOINT}/${slug}/projects`, {
        token: access_token,
        error: 'Error fetching campaign projects',
    })
}

export async function attach_campaign_project(slug:string, access_token:string, project_id:string) {
    return await api_request<null>(`${API_ENDPOINT}/${slug}/projects`, {
        method: 'POST',
        token: access_token,
        body: { project_id: project_id },
        error: 'Error fetching campaign project',
    })
}

export async function detach_campaign_project(slug:string, access_token:string, project_id:string) {
    return await api_request<null>(`${API_ENDPOINT}/${slug}/projects/${project_id}`, {
        method: 'DELETE',
        token: access_token,
        error: 'Error fetching campaign project',
    })
}
