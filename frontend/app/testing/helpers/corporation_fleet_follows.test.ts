import { describe, expect, it } from 'vitest'
import {
    fleet_follow_delivery_error_key,
    fleet_follow_error_key,
    fleet_follow_status_key,
    fleet_follow_warning_key,
    group_follow_decision,
    parse_fleet_follow_action,
} from '@helpers/corporations/fleet_follows_settings'
import { ui } from '@i18n/ui'

describe('corporation fleet follows', () => {
    it('reads the form action', () => {
        expect(parse_fleet_follow_action('save')).toBe('save')
        expect(parse_fleet_follow_action('remove')).toBe('remove')
        expect(parse_fleet_follow_action('other')).toBe('save')
        expect(parse_fleet_follow_action(null)).toBe('save')
    })

    it('maps every backend error code to a string, unknown ones to the generic error', () => {
        for (const code of ['not_eligible', 'not_connected', 'unknown_channel', 'discord_unreachable', 'unknown_group'])
            expect(ui.en[fleet_follow_error_key(code)]).toBeTruthy()
        expect(fleet_follow_error_key('nope')).toBe('corporations.settings.error_save')
    })

    it('has a label for each status and warning', () => {
        for (const status of ['requested', 'approved', 'revoked'])
            expect(ui.en[fleet_follow_status_key(status)]).toBeTruthy()
        for (const warning of ['channel_missing', 'cant_post', 'no_embeds', 'no_here'])
            expect(ui.en[fleet_follow_warning_key(warning)]).toBeTruthy()
    })

    it('names a deleted channel', () => {
        expect(fleet_follow_warning_key('channel_missing')).toBe('corporations.fleet_pings.warning_channel_missing')
    })

    it('says why the last post failed', () => {
        const keys = ['unknown_channel', 'missing_access', 'missing_permissions', 'error'].map(fleet_follow_delivery_error_key)
        for (const key of keys)
            expect(ui.en[key]).toBeTruthy()
        expect(new Set(keys).size).toBe(4)
        expect(fleet_follow_delivery_error_key('')).toBe('corporations.fleet_pings.delivery_error')
    })

    it('reads a chief decision, nothing else', () => {
        expect(group_follow_decision('approve')).toBe('approve')
        expect(group_follow_decision('revoke')).toBe('revoke')
        expect(group_follow_decision('delete')).toBeNull()
    })
})
