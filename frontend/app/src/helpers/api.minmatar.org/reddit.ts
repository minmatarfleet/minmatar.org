import type { CorporationRedditPost, CorporationRedditPostUpdate, RedditMarkdownProblem } from '@dtypes/api.minmatar.org'
import { api_request, api_response } from '@helpers/api.minmatar.org/client'

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

/** The corporation's post settings, or null when the user is not the CEO. */
export async function get_corporation_reddit_post(access_token: string, corporation_id: number) {
    return await api_request<CorporationRedditPost>(`${API_ENDPOINT}/corporations/${corporation_id}/post`, {
        token: access_token,
        allow: [403, 404],
    })
}

export async function update_corporation_reddit_post(
    access_token: string,
    corporation_id: number,
    payload: CorporationRedditPostUpdate,
) {
    const response = await api_response(`${API_ENDPOINT}/corporations/${corporation_id}/post`, {
        method: 'PUT',
        token: access_token,
        body: payload,
        allow: [400],
    })
    if (response.status === 400) {
        const body = await response.json().catch(() => ({}))
        throw new RedditSettingsError(body.detail ?? 'invalid', body.problems ?? [])
    }
    return await response.json() as CorporationRedditPost
}

export async function disconnect_reddit_account(access_token: string) {
    // 404: already disconnected, which is what the user wanted.
    await api_response(`${API_ENDPOINT}/account`, {
        method: 'DELETE',
        token: access_token,
        allow: [404],
    })
}

/** Browser-navigation URL that starts the Reddit OAuth link. */
export function reddit_connect_url(api_url: string, return_url: string, access_token: string) {
    return `${api_url}/api/reddit/connect` +
        `?redirect_url=${encodeURIComponent(return_url)}` +
        `&token=${encodeURIComponent(access_token)}`
}
