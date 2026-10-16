import type { CorporationRedditPost, RedditDeliveryMethod, RedditMarkdownProblemCode, RedditScheduleChange } from '@dtypes/api.minmatar.org'
import type { ui } from '@i18n/ui'

type UiKey = keyof typeof ui['en']

// Automatic posting from a linked Reddit account is switched off for now: the
// option shows as "Coming soon" and every save is a Discord reminder. Flip to
// re-enable; the backend already supports it.
export const REDDIT_AUTOMATIC_POSTING: boolean = false

/** The pause checkbox: checked means out of the rotation. */
export function parse_paused(value: unknown): boolean {
    return value === 'on' || value === 'true'
}

/** A timestamp in EVE time (UTC), e.g. "Thu, Oct 23, 17:00". */
export function format_eve_datetime(iso: string, locale: string = 'en'): string {
    return new Intl.DateTimeFormat(locale, {
        weekday: 'short',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
        hourCycle: 'h23',
        timeZone: 'UTC',
    }).format(new Date(iso))
}

/** The message for a slot the post gained or lost. */
export function reddit_change_key(change: Pick<RedditScheduleChange, 'gained'>): UiKey {
    return change.gained
        ? 'corporations.settings.change_gained'
        : 'corporations.settings.change_lost'
}

export function parse_delivery_method(value: unknown): RedditDeliveryMethod {
    return value === 'automatic' ? 'automatic' : 'discord_reminder'
}

export function is_corporation_slug(value: string | null | undefined): value is string {
    return /^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(value ?? '')
}

export interface RedditFlash {
    kind: 'success' | 'error';
    key: UiKey;
}

/** The message to show after the Reddit OAuth round trip, from the page URL. */
export function reddit_connect_flash(params: URLSearchParams): RedditFlash | null {
    if (params.get('reddit') === 'connected')
        return { kind: 'success', key: 'corporations.settings.reddit_connected' }
    const error = params.get('reddit_error')
    if (!error)
        return null
    return {
        kind: 'error',
        key: error === 'denied'
            ? 'corporations.settings.reddit_error_denied'
            : 'corporations.settings.reddit_error',
    }
}

const SAVE_ERRORS: Record<string, UiKey> = {
    markdown_invalid: 'corporations.settings.error_markdown',
    title_required: 'corporations.settings.error_title_required',
    title_too_long: 'corporations.settings.error_title_too_long',
    content_required: 'corporations.settings.error_content_required',
    content_too_long: 'corporations.settings.error_content_too_long',
}

export function reddit_save_error_key(code: string): UiKey {
    return SAVE_ERRORS[code] ?? 'corporations.settings.error_save'
}

const MARKDOWN_PROBLEMS: Record<RedditMarkdownProblemCode, UiKey> = {
    html: 'corporations.settings.markdown_html',
    image: 'corporations.settings.markdown_image',
    footnote: 'corporations.settings.markdown_footnote',
    task_list: 'corporations.settings.markdown_task_list',
    soft_line_break: 'corporations.settings.markdown_soft_line_break',
    fenced_code: 'corporations.settings.markdown_fenced_code',
    heading_space: 'corporations.settings.markdown_heading_space',
}

export function reddit_markdown_problem_key(code: RedditMarkdownProblemCode): UiKey {
    return MARKDOWN_PROBLEMS[code]
}

export const REDDIT_FORMATTING_GUIDE_URL = 'https://support.reddithelp.com/hc/en-us/articles/360043033952-Formatting-Guide'

/** One line for the collapsed Reddit section header, e.g. "Next: Thu, Nov 19, 14:20 EVE · Discord reminder". */
export function reddit_section_summary(
    settings: Pick<CorporationRedditPost, 'exists' | 'rotation_status' | 'upcoming' | 'delivery_method' | 'approved'>,
    labels: {
        not_set_up: string,
        paused: string,
        admin_paused: string,
        next: string,
        reminder: string,
        automatic: string,
        approved: string,
        awaiting: string,
    },
    locale: string = 'en',
): string {
    if (!settings.exists)
        return labels.not_set_up
    if (settings.rotation_status === 'paused')
        return labels.paused
    if (settings.rotation_status === 'admin_paused')
        return labels.admin_paused
    const parts: string[] = []
    const next = settings.upcoming[0]
    if (next)
        parts.push(labels.next.replace('~WHEN', format_eve_datetime(next.scheduled_for, locale)))
    if (settings.delivery_method !== 'automatic')
        return [...parts, labels.reminder].join(' · ')
    return [...parts, labels.automatic, settings.approved ? labels.approved : labels.awaiting].join(' · ')
}
