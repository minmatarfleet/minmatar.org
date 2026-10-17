import type { CorporationForumPost, CorporationForumPostUpdate } from '@dtypes/api.minmatar.org'
import { get_error_message } from '@helpers/string'

const API_ENDPOINT = `${import.meta.env.API_URL}/api/recruitment`

/** Thrown for a 400: `message` is the API's error code (e.g. `not_eve_forums`). */
export class ForumPostError extends Error {}

function auth_headers(access_token: string) {
    return {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${access_token}`,
    }
}

/** The corporation's linked forum thread, or null when the user is not the CEO. */
export async function get_corporation_forum_post(access_token: string, corporation_id: number) {
    const endpoint = `${API_ENDPOINT}/corporations/${corporation_id}/forum-post`
    const response = await fetch(endpoint, { headers: auth_headers(access_token) })
    if (response.status === 403 || response.status === 404)
        return null
    if (!response.ok) {
        throw new Error(get_error_message(response.status, `GET ${endpoint}`), {
            cause: response.status,
        })
    }
    return await response.json() as CorporationForumPost
}

/** Link or change the thread; an empty url removes the link. */
export async function update_corporation_forum_post(
    access_token: string,
    corporation_id: number,
    payload: CorporationForumPostUpdate,
) {
    const endpoint = `${API_ENDPOINT}/corporations/${corporation_id}/forum-post`
    const response = await fetch(endpoint, {
        method: 'PUT',
        headers: auth_headers(access_token),
        body: JSON.stringify(payload),
    })
    if (response.status === 400) {
        const body = await response.json().catch(() => ({}))
        throw new ForumPostError(body.detail ?? 'invalid')
    }
    if (!response.ok) {
        throw new Error(get_error_message(response.status, `PUT ${endpoint}`), {
            cause: response.status,
        })
    }
    return await response.json() as CorporationForumPost
}

/**
 * Record a visit through a recruitment scout reply's tracked link. Never
 * throws: the visitor is redirected whether or not the click was saved.
 */
export async function record_scout_click(code: string, target: string, client_ip: string, user_agent: string) {
    const endpoint = `${API_ENDPOINT}/scout/clicks`
    try {
        await fetch(endpoint, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ code, target, client_ip, user_agent }),
            signal: AbortSignal.timeout(1500),
        })
    } catch (error) {
        console.log(`POST ${endpoint} failed: ${error.message}`)
    }
}
