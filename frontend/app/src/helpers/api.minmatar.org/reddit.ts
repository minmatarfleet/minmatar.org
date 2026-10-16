import type { CorporationRedditPost, CorporationRedditPostUpdate, RedditMarkdownProblem } from '@dtypes/api.minmatar.org'
import { get_error_message } from '@helpers/string'

const API_ENDPOINT = `${import.meta.env.API_URL}/api/reddit`

/** Thrown for a 400: `message` is the API's error code (e.g. `title_required`);
 * `problems` lists the Markdown Reddit can't render. */
export class RedditSettingsError extends Error {
    problems: RedditMarkdownProblem[]

    constructor(code: string, problems: RedditMarkdownProblem[] = []) {
        super(code)
        this.problems = problems
    }
}

function auth_headers(access_token: string) {
    return {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${access_token}`,
    }
}

/** The corporation's post settings, or null when the user is not the CEO. */
export async function get_corporation_reddit_post(access_token: string, corporation_id: number) {
    const endpoint = `${API_ENDPOINT}/corporations/${corporation_id}/post`
    const response = await fetch(endpoint, { headers: auth_headers(access_token) })
    if (response.status === 403 || response.status === 404)
        return null
    if (!response.ok) {
        throw new Error(get_error_message(response.status, `GET ${endpoint}`), {
            cause: response.status,
        })
    }
    return await response.json() as CorporationRedditPost
}

export async function update_corporation_reddit_post(
    access_token: string,
    corporation_id: number,
    payload: CorporationRedditPostUpdate,
) {
    const endpoint = `${API_ENDPOINT}/corporations/${corporation_id}/post`
    const response = await fetch(endpoint, {
        method: 'PUT',
        headers: auth_headers(access_token),
        body: JSON.stringify(payload),
    })
    if (response.status === 400) {
        const body = await response.json().catch(() => ({}))
        throw new RedditSettingsError(body.detail ?? 'invalid', body.problems ?? [])
    }
    if (!response.ok) {
        throw new Error(get_error_message(response.status, `PUT ${endpoint}`), {
            cause: response.status,
        })
    }
    return await response.json() as CorporationRedditPost
}

export async function disconnect_reddit_account(access_token: string) {
    const endpoint = `${API_ENDPOINT}/account`
    const response = await fetch(endpoint, {
        method: 'DELETE',
        headers: auth_headers(access_token),
    })
    // 404: already disconnected, which is what the user wanted.
    if (!response.ok && response.status !== 404) {
        throw new Error(get_error_message(response.status, `DELETE ${endpoint}`), {
            cause: response.status,
        })
    }
}

/** Browser-navigation URL that starts the Reddit OAuth link. */
export function reddit_connect_url(api_url: string, return_url: string, access_token: string) {
    return `${api_url}/api/reddit/connect` +
        `?redirect_url=${encodeURIComponent(return_url)}` +
        `&token=${encodeURIComponent(access_token)}`
}
