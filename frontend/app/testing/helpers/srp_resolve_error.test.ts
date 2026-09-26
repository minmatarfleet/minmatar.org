import { describe, expect, it } from 'vitest'

import {
    srp_resolve_blocked_message,
    srp_resolve_is_blocked,
} from '@helpers/srp_resolve_error'

const translate = (key: string) => key

describe('srp_resolve_blocked_message', () => {
    it('explains a killmail character that is not on the account', () => {
        const message = srp_resolve_blocked_message(
            { message: 'Error resolving killmail: Character does not belong to user' },
            'https://esi.evetech.net/killmails/1/abc/',
            'dreads',
            translate,
        )
        expect(message).toBe('srp_character_not_on_account')
    })

    it('shows other resolve errors instead of a blank warning', () => {
        const message = srp_resolve_blocked_message(
            { message: 'Error resolving killmail: Primary character does not exist' },
            'https://esi.evetech.net/killmails/1/abc/',
            'dreads',
            translate,
        )
        expect(message).toBe('Error resolving killmail: Primary character does not exist')
    })

    it('falls back when the link or program is missing', () => {
        expect(srp_resolve_blocked_message(false, null, 'dreads', translate))
            .toBe('invalid_killmail_link')
        expect(srp_resolve_blocked_message(false, 'https://esi.evetech.net/killmails/1/abc/', null, translate))
            .toBe('invalid_srp_program')
    })
})

describe('srp_resolve_is_blocked', () => {
    it('blocks when the API error has a cause', () => {
        expect(srp_resolve_is_blocked(
            { cause: 403 },
            'https://esi.evetech.net/killmails/1/abc/',
            'dreads',
        )).toBe(true)
    })
})
