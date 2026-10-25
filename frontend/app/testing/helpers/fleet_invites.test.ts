import { describe, expect, it } from 'vitest'

import { invite_day, is_skipped, skip_note } from '@helpers/fleet_invites'
import { useTranslations } from '@i18n/utils'

const t = useTranslations('en')

describe('is_skipped', () => {
    it('lets weekly-capped and opted-out pilots be picked', () => {
        expect(is_skipped('capped')).toBe(true)
        expect(is_skipped('opted_out')).toBe(true)
    })

    it('keeps pilots already on this fleet unpickable', () => {
        expect(is_skipped('invited')).toBe(false)
        expect(is_skipped(null)).toBe(false)
    })
})

describe('skip_note', () => {
    it('names the fleet, when it was sent and when they are free again', () => {
        const note = skip_note(t, 'en', {
            blocked: 'capped',
            capped: {
                user_id: 7,
                name: 'Teysha Blackblade',
                fleet: 'Thursday Rifter roam',
                invited_at: '2026-10-23T18:42:00Z',
                free_at: '2026-10-30T18:42:00Z',
            },
        })
        expect(note).toContain('Thursday Rifter roam')
        expect(note).toContain(invite_day('en', '2026-10-23T18:42:00Z'))
        expect(note).toContain(invite_day('en', '2026-10-30T18:42:00Z'))
        expect(note).not.toContain('{')
    })

    it('says when a pilot turned fleet invites off', () => {
        expect(skip_note(t, 'en', { blocked: 'opted_out', capped: null })).toBe(t('fleets.invites.skip_opted_out'))
    })

    it('is empty for a pick the send keeps', () => {
        expect(skip_note(t, 'en', { blocked: null, capped: null })).toBe('')
        expect(skip_note(t, 'en', { blocked: 'invited', capped: null })).toBe('')
    })
})

describe('invite_day', () => {
    it('uses the EVE (UTC) day', () => {
        expect(invite_day('en', '2026-10-30T23:30:00Z')).toBe('Fri, Oct 30')
    })
})
