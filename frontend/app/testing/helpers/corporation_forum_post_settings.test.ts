import { describe, expect, it } from 'vitest'
import {
    forum_post_error_key,
    forum_post_link_text,
    forum_post_section_summary,
    parse_forum_post_action,
    RECRUITMENT_CENTER_URL,
} from '@helpers/corporations/forum_post_settings'
import { ui } from '@i18n/ui'

describe('corporation EVE forums recruitment thread', () => {
    it('only removes the link when asked to', () => {
        expect(parse_forum_post_action('remove')).toBe('remove')
        expect(parse_forum_post_action('save')).toBe('save')
        expect(parse_forum_post_action('delete_everything')).toBe('save')
        expect(parse_forum_post_action(null)).toBe('save')
    })

    it('has a message for every error code the API reports', () => {
        const codes = [
            'url_required',
            'invalid_url',
            'not_eve_forums',
            'not_a_thread',
            'not_recruitment_center',
            'thread_not_found',
            'thread_linked_elsewhere',
        ]
        for (const code of codes) {
            expect(forum_post_error_key(code)).not.toBe('corporations.settings.error_save')
            expect(ui.en[forum_post_error_key(code)]).toBeTruthy()
        }
        expect(forum_post_error_key('something_new')).toBe('corporations.settings.error_save')
    })

    it('falls back to the URL when the forum title is unknown', () => {
        const url = 'https://forums.eveonline.com/t/rattini-tribe-is-recruiting/496493'
        expect(forum_post_link_text({ title: 'Rattini Tribe is recruiting', url })).toBe('Rattini Tribe is recruiting')
        expect(forum_post_link_text({ title: '', url })).toBe(url)
        expect(forum_post_link_text({ title: '', url: null })).toBe('')
    })

    it('summarises the forum section for its collapsed header', () => {
        const labels = { not_linked: 'Not linked', linked: 'Linked' }
        expect(forum_post_section_summary({ exists: false, title: '' }, labels)).toBe('Not linked')
        expect(forum_post_section_summary({ exists: true, title: '' }, labels)).toBe('Linked')
        expect(forum_post_section_summary({ exists: true, title: 'Rattini Tribe is recruiting' }, labels))
            .toBe('Linked · Rattini Tribe is recruiting')
    })

    it('links the Recruitment Center category', () => {
        const url = new URL(RECRUITMENT_CENTER_URL)
        expect(url.hostname).toBe('forums.eveonline.com')
        expect(url.pathname.endsWith('/recruitment-center/63')).toBe(true)
    })
})
