import { describe, expect, it } from 'vitest'
import {
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
        for (const warning of ['cant_post', 'no_embeds', 'no_here'])
            expect(ui.en[fleet_follow_warning_key(warning)]).toBeTruthy()
    })

    it('reads a chief decision, nothing else', () => {
        expect(group_follow_decision('approve')).toBe('approve')
        expect(group_follow_decision('revoke')).toBe('revoke')
        expect(group_follow_decision('delete')).toBeNull()
    })
})
