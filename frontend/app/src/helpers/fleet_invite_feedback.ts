/**
 * The one-round fleet invite feedback form: load it, submit it, and read
 * the counts. Question text comes from the API. This file only moves it.
 */

import { api_request, api_response, read_json } from '@helpers/api.minmatar.org/client' // pragma: allowlist secret

const API_ENDPOINT = `${import.meta.env.API_URL}/api/fleets`

export interface InviteFeedbackChoice {
    key: string
    label: string
}

export interface InviteFeedbackQuestion {
    key: string
    prompt: string
    help: string
    kind: string
    badge: string
    choices: InviteFeedbackChoice[]
    exclusive: string
    max: number
}

export interface InviteFeedbackAnswers {
    felt: string
    sitting_out: string
    why: string
    why_text: string
    improve: string[]
    comment: string
}

export interface InviteFeedbackInvite {
    fleet_id: number
    when: string
    title: string
    answer: string
    answer_label: string
}

export interface InviteFeedbackForm {
    state: 'form' | 'thanks' | 'not_invited' | 'closed'
    heading: string
    body: string
    detail: string
    intro: string
    list_heading: string
    invites: InviteFeedbackInvite[]
    pending_invites: InviteFeedbackInvite[]
    questions: InviteFeedbackQuestion[]
    answers: InviteFeedbackAnswers
    comment_heading: string
    comment_placeholder: string
    errors: string[]
}

export interface InviteFeedbackBar {
    key: string
    label: string
    count: number
}

export interface InviteFeedbackSplit {
    key: string
    label: string
    count: number
    bars: InviteFeedbackBar[]
}

export interface InviteFeedbackFrameRow {
    key: string
    label: string
    asked_count: number
    asked_percent: number
    answered_count: number
    answered_percent: number
}

export interface InviteFeedbackChip {
    key: string
    label: string
    count: number
    active: boolean
}

export interface InviteFeedbackResults {
    show_link: boolean
    status: string
    lede: string
    cohort_count: number
    response_count: number
    answered_percent: number
    glad_or_fine_percent: number
    open_replied: number
    open_asked: number
    frame: InviteFeedbackFrameRow[]
    frame_note: string
    chips: InviteFeedbackChip[]
    cut: string
    sitting_out: InviteFeedbackBar[]
    sitting_out_split: InviteFeedbackSplit[]
    sitting_out_help: string
    felt: InviteFeedbackBar[]
    felt_split: InviteFeedbackSplit[]
    felt_help: string
    why: InviteFeedbackBar[]
    why_help: string
    improve: InviteFeedbackBar[]
    improve_help: string
    quotes: string[]
    quotes_help: string
}

export function answers_from_form(form: FormData): InviteFeedbackAnswers {
    return {
        felt: String(form.get('felt') ?? ''),
        sitting_out: String(form.get('sitting_out') ?? ''),
        why: String(form.get('why') ?? ''),
        why_text: String(form.get('why_text') ?? ''),
        improve: form.getAll('improve').map((value) => String(value)),
        comment: String(form.get('comment') ?? ''),
    }
}

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

export function bar_width(count: number, max: number) {
    if (!max) return '0%'
    return `${Math.round((100 * count) / max)}%`
}

export function bar_max(bars: InviteFeedbackBar[]) {
    return bars.reduce((max, bar) => Math.max(max, bar.count), 0)
}
