import { describe, expect, it } from 'vitest'
import {
    DISCORD_BOT_POLL_LIMIT,
    discord_bot_connect_flash,
    discord_bot_needs_attention,
    discord_bot_next_poll,
    discord_bot_status_key,
    discord_error_key,
    discord_invite_label,
    discord_section_summary,
    discord_server_initials,
    discord_status_key,
    parse_discord_action,
} from '@helpers/corporations/discord_settings'

const labels = { not_set: 'Optional · not set', set: 'Set', dead: 'Needs a new link' }

describe('discord_section_summary', () => {
    it('reads as optional when the corp has no Discord', () => {
        expect(discord_section_summary({ exists: false, status: null }, labels)).toBe('Optional · not set')
    })

    it('asks for a new link when the invite died', () => {
        expect(discord_section_summary({ exists: true, status: 'dead' }, labels)).toBe('Needs a new link')
    })

    it('is set while working or not checked yet', () => {
        expect(discord_section_summary({ exists: true, status: 'ok' }, labels)).toBe('Set')
        expect(discord_section_summary({ exists: true, status: 'unchecked' }, labels)).toBe('Set')
    })
})

describe('discord settings helpers', () => {
    it('maps backend error codes, falling back to the generic save error', () => {
        expect(discord_error_key('invite_expires')).toBe('corporations.discord.error_invite_expires')
        expect(discord_error_key('something_new')).toBe('corporations.settings.error_save')
    })

    it('maps statuses, treating unknown ones as unchecked', () => {
        expect(discord_status_key('ok')).toBe('corporations.discord.status_ok')
        expect(discord_status_key('dead')).toBe('corporations.discord.status_dead')
        expect(discord_status_key(null)).toBe('corporations.discord.status_unchecked')
    })

    it('parses form actions, defaulting to check', () => {
        expect(parse_discord_action('remove')).toBe('remove')
        expect(parse_discord_action('nonsense')).toBe('check')
        expect(parse_discord_action(null)).toBe('check')
    })

    it('shows invites the way people type them', () => {
        expect(discord_invite_label('https://discord.gg/rattini')).toBe('discord.gg/rattini')
        expect(discord_invite_label(null)).toBe('')
    })

    it('uses initials for servers without an icon', () => {
        expect(discord_server_initials('Rattini Tribe')).toBe('RT')
        expect(discord_server_initials('rats')).toBe('R')
        expect(discord_server_initials(null)).toBe('#')
    })
})

describe('discord bot', () => {
    const bot_labels = { ...labels, setting_up: 'Setting up', attention: 'Needs attention' }

    it('summarises the bot before the pasted link', () => {
        const pasted = { exists: true, status: 'dead' }
        expect(discord_section_summary({ ...pasted, bot: { connected: true, status: 'ok' } }, bot_labels)).toBe('Set')
        expect(discord_section_summary({ ...pasted, bot: { connected: true, status: 'pending' } }, bot_labels)).toBe('Setting up')
        expect(discord_section_summary({ ...pasted, bot: { connected: true, status: 'removed' } }, bot_labels)).toBe('Needs attention')
        expect(discord_section_summary({ ...pasted, bot: { connected: false, status: null } }, bot_labels)).toBe('Needs a new link')
    })

    it('asks for attention only when the bot makes no invites', () => {
        expect(discord_bot_needs_attention('no_permission')).toBe(true)
        expect(discord_bot_needs_attention('removed')).toBe(true)
        expect(discord_bot_needs_attention('pending')).toBe(false)
        expect(discord_bot_needs_attention('ok')).toBe(false)
        expect(discord_bot_status_key('removed')).toBe('corporations.discord.bot_status_removed')
    })

    it('reports the return from the install page', () => {
        expect(discord_bot_connect_flash(new URLSearchParams('discord_bot=connected')))
            .toEqual({ kind: 'success', key: 'corporations.discord.bot_connected' })
        expect(discord_bot_connect_flash(new URLSearchParams('discord_bot_error=alliance_server')))
            .toEqual({ kind: 'error', key: 'corporations.discord.bot_error_alliance_server' })
        expect(discord_bot_connect_flash(new URLSearchParams('discord_bot_error=exchange_failed')))
            .toEqual({ kind: 'error', key: 'corporations.discord.bot_error' })
        expect(discord_bot_connect_flash(new URLSearchParams(''))).toBeNull()
    })

    it('polls only while setting up, and gives up', () => {
        expect(discord_bot_next_poll('pending', 0)).toBe(1)
        expect(discord_bot_next_poll('pending', DISCORD_BOT_POLL_LIMIT)).toBeNull()
        expect(discord_bot_next_poll('ok', 3)).toBeNull()
    })

    it('knows the bot actions', () => {
        expect(parse_discord_action('disconnect_bot')).toBe('disconnect_bot')
        expect(parse_discord_action('retry_bot')).toBe('retry_bot')
    })
})
