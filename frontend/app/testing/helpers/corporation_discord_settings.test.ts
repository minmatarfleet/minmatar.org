import { describe, expect, it } from 'vitest'
import {
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
