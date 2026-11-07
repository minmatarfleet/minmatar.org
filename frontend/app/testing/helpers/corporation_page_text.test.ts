import { describe, expect, it } from 'vitest'

import {
    is_page_text_field,
    page_text_error_key,
    page_text_summary,
} from '@helpers/corporations/page_text'
import { reddit_save_error_key } from '@helpers/corporations/reddit_settings'

describe('corporation page text', () => {
    it('summarises the headline, cut short', () => {
        expect(page_text_summary('', 'No headline yet')).toBe('No headline yet')
        expect(page_text_summary('  We fly.  ', 'x')).toBe('We fly.')
        expect(page_text_summary('a'.repeat(100), 'x', 10)).toBe(`${'a'.repeat(9)}…`)
    })

    it('maps refused saves to messages', () => {
        expect(page_text_error_key('profanity')).toBe('corporations.page_text.error_profanity')
        expect(page_text_error_key('too_long')).toBe('corporations.page_text.error_too_long')
        expect(page_text_error_key('teapot')).toBe('corporations.settings.error_save')
    })

    it('knows its fields', () => {
        expect(is_page_text_field('highlights')).toBe(true)
        expect(is_page_text_field('requirements')).toBe(false)
    })

    it('names profanity in a Reddit save', () => {
        expect(reddit_save_error_key('title_profanity')).toBe('corporations.settings.error_title_profanity')
        expect(reddit_save_error_key('content_profanity')).toBe('corporations.settings.error_content_profanity')
    })
})
