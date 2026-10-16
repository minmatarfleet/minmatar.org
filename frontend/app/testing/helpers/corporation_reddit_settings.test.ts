import { describe, expect, it } from 'vitest'
import {
    format_eve_datetime,
    is_corporation_slug,
    parse_delivery_method,
    parse_paused,
    reddit_change_key,
    reddit_connect_flash,
    reddit_markdown_problem_key,
    reddit_save_error_key,
    reddit_section_summary,
} from '@helpers/corporations/reddit_settings'
import { ui } from '@i18n/ui'
import { reddit_connect_url } from '@helpers/api.minmatar.org/reddit'

describe('corporation Reddit settings', () => {
    it('reads the pause checkbox', () => {
        expect(parse_paused('on')).toBe(true)
        expect(parse_paused('true')).toBe(true)
        expect(parse_paused(null)).toBe(false)
        expect(parse_paused('')).toBe(false)
    })

    it('has a message for slots gained and lost', () => {
        expect(ui.en[reddit_change_key({ gained: true })]).toContain('~DATE')
        expect(ui.en[reddit_change_key({ gained: false })]).toContain('~DATE')
    })

    it('shows times in EVE time whatever the server timezone', () => {
        const label = format_eve_datetime('2026-10-22T17:00:00Z')
        expect(label).toContain('17:00')
        expect(label).toContain('Thu')
        expect(format_eve_datetime('2026-10-22T23:30:00+00:00')).toContain('23:30')
    })

    it('only accepts known delivery methods', () => {
        expect(parse_delivery_method('automatic')).toBe('automatic')
        expect(parse_delivery_method('discord_reminder')).toBe('discord_reminder')
        expect(parse_delivery_method('carrier_pigeon')).toBe('discord_reminder')
        expect(parse_delivery_method(null)).toBe('discord_reminder')
    })

    it('only builds return paths from slugs', () => {
        expect(is_corporation_slug('rattini-tribe')).toBe(true)
        expect(is_corporation_slug('98726134')).toBe(true)
        expect(is_corporation_slug('../admin')).toBe(false)
        expect(is_corporation_slug('https://evil.example')).toBe(false)
        expect(is_corporation_slug('')).toBe(false)
        expect(is_corporation_slug(null)).toBe(false)
    })

    it('reports the Reddit link round trip', () => {
        expect(reddit_connect_flash(new URLSearchParams('reddit=connected'))).toEqual({
            kind: 'success',
            key: 'corporations.settings.reddit_connected',
        })
        expect(reddit_connect_flash(new URLSearchParams('reddit_error=denied&id=X'))?.key)
            .toBe('corporations.settings.reddit_error_denied')
        expect(reddit_connect_flash(new URLSearchParams('reddit_error=state_mismatch'))?.key)
            .toBe('corporations.settings.reddit_error')
        expect(reddit_connect_flash(new URLSearchParams(''))).toBeNull()
    })

    it('maps save errors to messages', () => {
        expect(reddit_save_error_key('title_required')).toBe('corporations.settings.error_title_required')
        expect(reddit_save_error_key('content_too_long')).toBe('corporations.settings.error_content_too_long')
        expect(reddit_save_error_key('something_new')).toBe('corporations.settings.error_save')
    })

    it('passes the return URL and token to the connect endpoint', () => {
        const url = new URL(reddit_connect_url(
            'https://api.minmatar.org',
            'https://my.minmatar.org/alliance/corporations/rattini-tribe/#settings',
            'jwt.token',
        ))
        expect(url.pathname).toBe('/api/reddit/connect')
        expect(url.searchParams.get('redirect_url'))
            .toBe('https://my.minmatar.org/alliance/corporations/rattini-tribe/#settings')
        expect(url.searchParams.get('token')).toBe('jwt.token')
    })

    it('has a message for every Markdown problem the API reports', () => {
        const codes = ['html', 'image', 'footnote', 'task_list', 'soft_line_break', 'fenced_code', 'heading_space'] as const
        for (const code of codes)
            expect(ui.en[reddit_markdown_problem_key(code)]).toBeTruthy()
        expect(reddit_save_error_key('markdown_invalid')).toBe('corporations.settings.error_markdown')
    })

    it('summarises the Reddit section for its collapsed header', () => {
        const labels = {
            not_set_up: 'Not set up',
            paused: 'Paused',
            admin_paused: 'Paused by an admin',
            next: 'Next: ~WHEN EVE',
            reminder: 'Discord reminder',
            automatic: 'Automatic',
            approved: 'Approved',
            awaiting: 'Awaiting approval',
        }
        const base = {
            exists: true,
            rotation_status: 'active' as const,
            upcoming: [{ scheduled_for: '2026-11-19T14:20:00Z', confirmed: true }],
            delivery_method: 'automatic' as const,
            approved: true,
        }
        const next = `Next: ${format_eve_datetime('2026-11-19T14:20:00Z')} EVE`
        expect(reddit_section_summary(base, labels)).toBe(`${next} · Automatic · Approved`)
        expect(reddit_section_summary({ ...base, approved: false }, labels)).toBe(`${next} · Automatic · Awaiting approval`)
        expect(reddit_section_summary({ ...base, delivery_method: 'discord_reminder' }, labels)).toBe(`${next} · Discord reminder`)
        expect(reddit_section_summary({ ...base, upcoming: [] }, labels)).toBe('Automatic · Approved')
        expect(reddit_section_summary({ ...base, rotation_status: 'paused' }, labels)).toBe('Paused')
        expect(reddit_section_summary({ ...base, rotation_status: 'admin_paused' }, labels)).toBe('Paused by an admin')
        expect(reddit_section_summary({ ...base, exists: false }, labels)).toBe('Not set up')
    })
})
