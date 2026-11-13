/**
 * Types and form parsing for the one-round fleet invite feedback form.
 * Fetches live in the API helpers, which are the only place that reads API_URL.
 */

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
    keep: string
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
    keep: InviteFeedbackBar[]
    quotes: string[]
    quotes_help: string
}

export function answers_from_form(form: FormData): InviteFeedbackAnswers {
    return {
        felt: String(form.get('felt') ?? ''),
        sitting_out: String(form.get('sitting_out') ?? ''),
        why: String(form.get('why') ?? ''),
        why_text: String(form.get('why_text') ?? ''),
        keep: String(form.get('keep') ?? ''),
        comment: String(form.get('comment') ?? ''),
    }
}

export function bar_width(count: number, max: number) {
    if (!max) return '0%'
    return `${Math.round((100 * count) / max)}%`
}

export function bar_max(bars: InviteFeedbackBar[]) {
    return bars.reduce((max, bar) => Math.max(max, bar.count), 0)
}
