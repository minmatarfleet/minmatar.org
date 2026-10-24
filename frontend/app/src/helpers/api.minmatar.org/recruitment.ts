import type { CorporationForumPost, CorporationForumPostUpdate } from '@dtypes/api.minmatar.org'
import { api_request, api_response } from '@helpers/api.minmatar.org/client'
import { get_shared_secret } from '@helpers/env'

const API_ENDPOINT = `${import.meta.env.API_URL}/api/recruitment`

/** Thrown for a 400: `message` is the API's error code (e.g. `not_eve_forums`). */
export class ForumPostError extends Error {}

/** The corporation's linked forum thread, or null when the user is not the CEO. */
export async function get_corporation_forum_post(access_token: string, corporation_id: number) {
    return await api_request<CorporationForumPost>(`${API_ENDPOINT}/corporations/${corporation_id}/forum-post`, {
        token: access_token,
        allow: [403, 404],
    })
}

/** Link or change the thread; an empty url removes the link. */
export async function update_corporation_forum_post(
    access_token: string,
    corporation_id: number,
    payload: CorporationForumPostUpdate,
) {
    const response = await api_response(`${API_ENDPOINT}/corporations/${corporation_id}/forum-post`, {
        method: 'PUT',
        token: access_token,
        body: payload,
        allow: [400],
    })
    if (response.status === 400) {
        const body = await response.json().catch(() => ({}))
        throw new ForumPostError(body.detail ?? 'invalid')
    }
    return await response.json() as CorporationForumPost
}

/**
 * Record a visit through a recruitment scout reply's tracked link. Never
 * throws: the visitor is redirected whether or not the click was saved.
 *
 * Server-side only: the API accepts clicks from the frontend server, which
 * proves itself with the shared secret.
 */
export async function record_scout_click(code: string, target: string, client_ip: string, user_agent: string) {
    const endpoint = `${API_ENDPOINT}/scout/clicks`
    try {
        await api_response(endpoint, {
            method: 'POST',
            headers: { 'X-Shared-Secret': get_shared_secret() ?? '' },
            body: { code, target, client_ip, user_agent },
            signal: AbortSignal.timeout(1500),
        })
    } catch (error) {
        console.log(`POST ${endpoint} failed: ${error.message}`)
    }
}
