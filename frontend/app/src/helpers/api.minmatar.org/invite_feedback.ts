/**
 * Server fetches for the one-round fleet invite feedback form.
 * API_URL stays in this directory; see testing/helpers/api_url_usage.test.ts.
 */

import type {
    InviteFeedbackAnswers,
    InviteFeedbackForm,
    InviteFeedbackResults,
} from '@helpers/fleet_invite_feedback'
import { api_request, api_response, read_json } from '@helpers/api.minmatar.org/client' // pragma: allowlist secret

const API_ENDPOINT = `${import.meta.env.API_URL}/api/fleets`

export async function get_invite_feedback(access_token: string, edit = false) {
    const query = edit ? '?edit=true' : ''
    return await api_request<InviteFeedbackForm>(`${API_ENDPOINT}/invite-feedback${query}`, {
        token: access_token,
        error: 'Error opening the fleet invite form',
    })
}

export async function submit_invite_feedback(access_token: string, answers: InviteFeedbackAnswers) {
    const response = await api_response(`${API_ENDPOINT}/invite-feedback`, {
        method: 'POST',
        token: access_token,
        body: answers,
        allow: [400],
        error: 'Error saving fleet invite feedback',
    })
    const payload = await read_json<InviteFeedbackForm & { errors?: string[], detail?: string }>(response)
    if (response.status === 400) {
        const errors = payload?.errors?.length
            ? payload.errors
            : [payload?.detail ?? 'Try again.']
        return { ok: false as const, errors }
    }
    return { ok: true as const, form: payload as InviteFeedbackForm }
}

/** Whether upcoming fleets should show the results link. Strategic FCs only. */
export async function invite_feedback_show_link(access_token: string) {
    const payload = await api_request<InviteFeedbackResults>(
        `${API_ENDPOINT}/invite-feedback/results?link=true`,
        {
            token: access_token,
            error: 'Error checking invite feedback',
        },
    )
    return Boolean(payload?.show_link)
}

export async function get_invite_feedback_results(access_token: string, cut = 'all') {
    const query = cut && cut !== 'all' ? `?cut=${encodeURIComponent(cut)}` : ''
    return await api_request<InviteFeedbackResults>(
        `${API_ENDPOINT}/invite-feedback/results${query}`,
        {
            token: access_token,
            error: 'Error loading invite feedback',
        },
    )
}
