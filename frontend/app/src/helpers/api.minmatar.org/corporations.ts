import type { Corporation, CorporationType, CorporationInfo, CorporationMemberDetails, CorporationOpenApplication, CorporationProjects, CorporationDiscordSettings, CorporationDiscordInvitePreview, CorporationMemberPromote, MemberInsights } from '@dtypes/api.minmatar.org'
import { api_request, api_response } from '@helpers/api.minmatar.org/client'

const API_ENDPOINT =  `${import.meta.env.API_URL}/api/eveonline/corporations`

export async function get_all_corporations(corporation_type:CorporationType) {
    return await api_request<Corporation[]>(`${API_ENDPOINT}/corporations?corporation_type=${corporation_type}`, {
        error: 'Error fetching corporations',
    })
}

export async function get_corporation_by_id(access_token:string, id:number) {
    return await api_request<Corporation>(`${API_ENDPOINT}/corporations/${id}`, {
        token: access_token,
        error: 'Error fetching corporation',
    })
}

export async function get_corporation_info(id:number) {
    return await api_request<CorporationInfo>(`${API_ENDPOINT}/corporations/${id}/info`, {
        error: 'Error fetching corporation',
    })
}

export async function get_corporation_members(access_token: string, id: number) {
    const endpoint = `${API_ENDPOINT}/corporations/${id}/members`
    return await api_request<CorporationMemberDetails[] | null>(endpoint, {
        token: access_token,
        allow: [403, 404],
    })
}

export async function get_corporation_member_insights(access_token: string, id: number, character_id: number) {
    return await api_request<MemberInsights>(`${API_ENDPOINT}/corporations/${id}/members/${character_id}/insights`, {
        token: access_token,
        error: 'Error fetching member insights',
    })
}

/** Move a trial member to active (CEO, directors, People team). */
export async function promote_corporation_member(access_token: string, id: number, character_id: number) {
    return await api_request<CorporationMemberPromote>(`${API_ENDPOINT}/corporations/${id}/members/${character_id}/promote`, {
        method: 'POST',
        token: access_token,
        error: 'Error promoting member',
    })
}

export async function get_corporation_id_by_slug(slug: string) {
    return await api_request<{ corporation_id: number, slug: string } | null>(`${API_ENDPOINT}/corporations/by-slug/${encodeURIComponent(slug)}`, {
        allow: [404],
    })
}

export async function get_corporation_member_access(access_token: string, id: number) {
    const endpoint = `${API_ENDPOINT}/corporations/${id}/members/access`
    return await api_request<{
        can_view_members: boolean,
        can_view_characters: boolean,
        can_edit_settings?: boolean,
        can_view_projects?: boolean,
        can_manage_projects?: boolean,
    } | null>(endpoint, {
        token: access_token,
        allow: [403, 404],
    })
}

export async function get_corporation_open_applications(access_token: string, id: number) {
    const endpoint = `${API_ENDPOINT}/corporations/${id}/applications/open`
    return await api_request<CorporationOpenApplication[] | null>(endpoint, {
        token: access_token,
        allow: [403, 404],
    })
}
export async function get_corporation_projects(access_token: string, id: number) {
    const endpoint = `${API_ENDPOINT}/corporations/${id}/projects`
    return await api_request<CorporationProjects | null>(endpoint, {
        token: access_token,
        allow: [403, 404],
    })
}

/** Queue a sync from ESI. Resolves to the API status: 202 queued, 409 no token, 429 already pending. */
export async function refresh_corporation_projects(access_token: string, id: number) {
    const endpoint = `${API_ENDPOINT}/corporations/${id}/projects/refresh`
    const response = await api_response(endpoint, {
        method: 'POST',
        token: access_token,
        allow: [409, 429],
    })
    if (![202, 409, 429].includes(response.status)) {
        throw new Error(`HTTP error! Status — ${response.status}`, {
            cause: response.status,
        })
    }
    return response.status
}

/** Thrown for a 400: `message` is the API's error code (e.g. `invite_expires`). */
export class DiscordInviteError extends Error {}

async function discord_invite_request<T>(access_token: string, endpoint: string, method: string, invite_url?: string) {
    const response = await api_response(endpoint, {
        method,
        token: access_token,
        body: invite_url === undefined ? undefined : { invite_url },
        allow: [400],
    })
    if (response.status === 400) {
        const body = await response.json().catch(() => ({}))
        throw new DiscordInviteError(body.detail ?? 'invalid')
    }
    return await response.json() as T
}

/** The corporation's Discord server, or null when the user can't edit settings. */
export async function get_corporation_discord(access_token: string, corporation_id: number) {
    return await api_request<CorporationDiscordSettings>(`${API_ENDPOINT}/corporations/${corporation_id}/discord`, {
        token: access_token,
        allow: [403, 404],
    })
}

/** What Discord says about an invite, without saving it. */
export async function check_corporation_discord(access_token: string, corporation_id: number, invite_url: string) {
    return await discord_invite_request<CorporationDiscordInvitePreview>(
        access_token, `${API_ENDPOINT}/corporations/${corporation_id}/discord/check`, 'POST', invite_url,
    )
}

export async function update_corporation_discord(access_token: string, corporation_id: number, invite_url: string) {
    return await discord_invite_request<CorporationDiscordSettings>(
        access_token, `${API_ENDPOINT}/corporations/${corporation_id}/discord`, 'PUT', invite_url,
    )
}

export async function remove_corporation_discord(access_token: string, corporation_id: number) {
    return await discord_invite_request<CorporationDiscordSettings>(
        access_token, `${API_ENDPOINT}/corporations/${corporation_id}/discord`, 'DELETE',
    )
}

/** Browser URL that starts adding the bot (Discord's install page, then back to Settings). */
export function corporation_discord_bot_connect_url(api_url: string, corporation_id: number, access_token: string) {
    return `${api_url}/api/eveonline/corporations/corporations/${corporation_id}/discord/bot/connect` +
        `?token=${encodeURIComponent(access_token)}`
}

/** Stop using the bot; the pasted link, if any, becomes the page's Discord again. */
export async function disconnect_corporation_discord_bot(access_token: string, corporation_id: number) {
    return await discord_invite_request<CorporationDiscordSettings>(
        access_token, `${API_ENDPOINT}/corporations/${corporation_id}/discord/bot`, 'DELETE',
    )
}

/** Ask the bot to set up its invite again (after the server fixed its permissions). */
export async function retry_corporation_discord_bot(access_token: string, corporation_id: number) {
    return await discord_invite_request<CorporationDiscordSettings>(
        access_token, `${API_ENDPOINT}/corporations/${corporation_id}/discord/bot/refresh`, 'POST',
    )
}
