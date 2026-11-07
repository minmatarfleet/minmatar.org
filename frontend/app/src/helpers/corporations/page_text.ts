import type { ui } from '@i18n/ui'

type UiKey = keyof typeof ui['en']

export const PAGE_TEXT_FIELDS = ['introduction', 'biography', 'highlights', 'activity_summary'] as const
export type PageTextField = typeof PAGE_TEXT_FIELDS[number]

const FIELD_LABELS: Record<PageTextField, UiKey> = {
    introduction: 'corporations.page_text.introduction',
    biography: 'corporations.page_text.biography',
    highlights: 'corporations.page_text.highlights',
    activity_summary: 'corporations.page_text.activity_summary',
}

export function page_text_label_key(field: PageTextField): UiKey {
    return FIELD_LABELS[field]
}

export function is_page_text_field(value: string): value is PageTextField {
    return (PAGE_TEXT_FIELDS as readonly string[]).includes(value)
}

/** The message for a refused save; it takes ~FIELD and ~WORDS. */
export function page_text_error_key(code: string): UiKey {
    if (code === 'profanity') return 'corporations.page_text.error_profanity'
    if (code === 'too_long') return 'corporations.page_text.error_too_long'
    return 'corporations.settings.error_save'
}

/** The collapsed section's header: the headline, cut short, or a nudge. */
export function page_text_summary(introduction: string, empty: string, max_length: number = 70): string {
    const headline = introduction.trim()
    if (!headline) return empty
    return headline.length > max_length
        ? `${headline.slice(0, max_length - 1).trimEnd()}…`
        : headline
}
