/**
 * Server fetches for the fleet invite sign-up link (I'm available in
 * Discord). No login: the signed token in the path is the only key, so no
 * Authorization header is sent. A bad, expired or forwarded link, or a fleet
 * that already started, answers 410 (sometimes 400/403); callers show the
 * expired screen for those and never learn which fleet it was.
 * API_URL stays in this directory; see testing/helpers/api_url_usage.test.ts.
 */

import type { RsvpForm, RsvpResult, RsvpSubmit } from '@dtypes/api.minmatar.org'
import { api_response, format_response_detail, read_json } from '@helpers/api.minmatar.org/client' // pragma: allowlist secret
import { is_rsvp_token } from '@helpers/fleet_rsvp'

const API_ENDPOINT = `${import.meta.env.API_URL}/api/fleets/rsvp`

/** Statuses the backend uses for a link that can't be answered. */
const REFUSED = [400, 403, 404, 410]

export type RsvpOutcome<Type> =
    | { ok: true, data: Type }
    | { ok: false, status: number, detail: string }

async function rsvp_call<Type>(path: string, token: string, method: string, body?: unknown, error = 'Error loading the sign-up link'): Promise<RsvpOutcome<Type>> {
    if (!is_rsvp_token(token))
        return { ok: false, status: 410, detail: '' }

    const response = await api_response(`${API_ENDPOINT}/${encodeURIComponent(token)}${path}`, {
        method,
        body,
        allow: REFUSED,
        error,
    })
    const payload = await read_json<Type & { detail?: unknown }>(response)
    if (!response.ok)
        return { ok: false, status: response.status, detail: format_response_detail(payload?.detail) ?? '' }

    return { ok: true, data: payload as Type }
}

/** The sign-up form behind the link the bot DMs. */
export async function get_rsvp_form(token: string) {
    return await rsvp_call<RsvpForm>('', token, 'GET')
}

/** Sign up with the form's `submit_token` (not the link's token). */
export async function submit_rsvp(submit_token: string, body: RsvpSubmit) {
    return await rsvp_call<RsvpResult>('', submit_token, 'POST', body, 'Error saving the sign-up')
}

/** I'm not available, with the form's `submit_token`. Only skips this fleet. */
export async function rsvp_not_available(submit_token: string) {
    return await rsvp_call<RsvpResult>('/not-available', submit_token, 'POST', undefined, 'Error saving the answer')
}
