import { describe, expect, it } from 'vitest'
import { ui } from '@i18n/ui'
import {
    DISCORD_BOT_POLL_LIMIT,
    discord_bot_connect_flash,
    discord_bot_needs_attention,
    discord_bot_next_poll,
    discord_bot_status_key,
    discord_error_key,
    discord_invite_label,
    discord_roles_next_poll,
    discord_roles_refresh_pending,
    discord_section_summary,
    discord_server_initials,
    discord_status_key,
    discord_access_roles,
    discord_initial_action,
    discord_removal_eta,
    keep_member_action,
    parse_discord_action,
    parse_exemptions,
    parse_keep_member,
    parse_member_action,
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
        expect(discord_bot_connect_flash(new URLSearchParams('discord_bot_error=guild_taken')))
            .toEqual({ kind: 'error', key: 'corporations.discord.bot_error_guild_taken' })
        expect(discord_bot_connect_flash(new URLSearchParams('discord_bot_error=exchange_failed')))
            .toEqual({ kind: 'error', key: 'corporations.discord.bot_error' })
        expect(discord_bot_connect_flash(new URLSearchParams(''))).toBeNull()
    })

    it('polls only while setting up, and gives up', () => {
        expect(discord_bot_next_poll('pending', 0)).toBe(1)
        expect(discord_bot_next_poll('pending', DISCORD_BOT_POLL_LIMIT)).toBeNull()
        expect(discord_bot_next_poll('ok', 3)).toBeNull()
    })

    it('keeps polling a role refresh until the catalog is newer', () => {
        const since = '2026-11-12T13:42:09.123456Z'
        expect(discord_roles_refresh_pending(since, since)).toBe(true)
        expect(discord_roles_refresh_pending('2026-11-12T13:42:09.123Z', since)).toBe(true)
        expect(discord_roles_refresh_pending('2026-11-12T13:42:10Z', since)).toBe(false)
        expect(discord_roles_refresh_pending(null, since)).toBe(true)
        expect(discord_roles_refresh_pending('not-a-time', since)).toBe(true)
        expect(discord_roles_refresh_pending(since, null)).toBe(false)
        expect(discord_roles_refresh_pending(since, 'not-a-time')).toBe(false)
        expect(discord_roles_next_poll(true, 0)).toBe(1)
        expect(discord_roles_next_poll(true, DISCORD_BOT_POLL_LIMIT)).toBeNull()
        expect(discord_roles_next_poll(false, 1)).toBeNull()
    })

    it('knows the bot actions', () => {
        expect(parse_discord_action('disconnect_bot')).toBe('disconnect_bot')
        expect(parse_discord_action('retry_bot')).toBe('retry_bot')
        expect(parse_discord_action('save_roles')).toBe('save_roles')
        expect(parse_discord_action('refresh_roles')).toBe('refresh_roles')
        expect(ui.en['corporations.discord.roles_refresh']).toBe('Refresh roles')
        expect(ui.en['corporations.discord.roles_refreshed']).toBe('Roles updated.')
        expect(ui.en['tribes.discord.roles_refresh']).toBe('Refresh roles')
        expect(ui.en['tribes.discord.roles_refreshed']).toBe('Roles updated.')
        expect(ui.en['corporations.detail.role_steward']).toBe('Structure manager')
        expect(ui.en['corporations.detail.stewards']).toBe('Structure managers')
        expect(ui.en['corporations.discord.role_structure_manager']).toContain('Structure manager')
    })
})

describe('member access helpers', () => {
    it('round-trips a Keep button and refuses anything else', () => {
        expect(parse_keep_member(keep_member_action('123456789012345678'))).toBe('123456789012345678')
        expect(parse_keep_member('keep:abc')).toBeNull()
        expect(parse_keep_member('save_members')).toBeNull()
        expect(parse_discord_action('save_members')).toBe('save_members')
        expect(parse_discord_action('approve_members')).toBe('approve_members')
    })

    it('reads exemptions one per line or comma separated', () => {
        expect(parse_exemptions(' pal \n\nbuddy, other ')).toEqual(['pal', 'buddy', 'other'])
        expect(parse_exemptions(null)).toEqual([])
    })

    it('shows time left until removal, then nothing once due', () => {
        const now = Date.UTC(2026, 10, 13, 12, 0)
        expect(discord_removal_eta(new Date(now + 90 * 60_000).toISOString(), now)).toBe('1h 30m')
        expect(discord_removal_eta(new Date(now + 5 * 60_000).toISOString(), now)).toBe('5m')
        expect(discord_removal_eta(new Date(now + 72 * 3_600_000).toISOString(), now)).toBe('3d')
        expect(discord_removal_eta(new Date(now - 60_000).toISOString(), now)).toBeNull()
    })

    it('maps the member policy errors', () => {
        expect(discord_error_key('cannot_kick_members')).toBe('corporations.discord.error_cannot_kick_members')
        expect(discord_error_key('invalid_username')).toBe('corporations.discord.error_invalid_username')
    })
})

describe('discord_access_roles', () => {
    it('shows only the member role until others are added', () => {
        const roles = discord_access_roles([])
        expect(roles.all[0]).toBe('member')
        expect(roles.extra).not.toContain('member')
        expect(roles.added).toEqual([])
    })

    it('keeps roles that are already set on screen', () => {
        const roles = discord_access_roles([
            { state: 'member', role_id: '1' },
            { state: 'alliance_member', role_id: '2' },
            { state: 'director', role_id: null },
        ])
        expect(roles.added).toEqual(['alliance_member'])
    })
})

describe('parse_member_action', () => {
    it('reads the cleanup choice, and anything else as leave them', () => {
        expect(parse_member_action('notify')).toBe('notify')
        expect(parse_member_action('remove')).toBe('remove')
        expect(parse_member_action('')).toBeNull()
        expect(parse_member_action('kick')).toBeNull()
    })

    it('knows the one Save action', () => {
        expect(parse_discord_action('save_access')).toBe('save_access')
    })
})

describe('discord_initial_action', () => {
    it('starts a new policy on Notify the CEO', () => {
        expect(discord_initial_action(null, null)).toBe('notify')
    })

    it('keeps a saved choice, including remove roles only', () => {
        expect(discord_initial_action('corporation', 'remove')).toBe('remove')
        expect(discord_initial_action('corporation', null)).toBe('')
    })

    it('reads a policy from before actions existed as remove', () => {
        expect(discord_initial_action('alliance', undefined)).toBe('remove')
    })
})
