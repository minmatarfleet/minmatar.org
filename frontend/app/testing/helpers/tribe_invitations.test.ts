import { describe, expect, it } from 'vitest'

import type { TribeInvitation, TribeInvitationCandidate } from '@dtypes/api.minmatar.org'
import { i18n } from '@helpers/i18n'
import {
    candidate_reason,
    invitation_detail,
    invitation_dm_undelivered,
    invitation_status_label,
    invitation_tone,
    open_invitation_for_group,
} from '@helpers/tribe_invitations'
import { ui } from '@i18n/ui'

const { t } = i18n(new URL('https://my.minmatar.org/'))
const has_key = (key: string) => Object.prototype.hasOwnProperty.call(ui.en, key)

function invitation(overrides: Partial<TribeInvitation> = {}): TribeInvitation {
    return {
        id: 1,
        tribe_id: 1,
        tribe_name: 'Capitals',
        tribe_group_id: 1,
        tribe_group_name: 'Dreads',
        user_id: 2,
        character_id: 91002,
        character_name: 'Teysha Blackblade',
        invited_by_id: 3,
        invited_by_character_id: 91001,
        invited_by_name: 'Casper Sullivan',
        note: '',
        status: 'pending',
        created_at: '2026-10-23T19:12:00Z',
        expires_at: '2026-11-06T19:12:00Z',
        responded_at: null,
        joined_character_count: null,
        dm_status: 'sent',
        dm_error: '',
        ...overrides,
    }
}

function candidate(overrides: Partial<TribeInvitationCandidate> = {}): TribeInvitationCandidate {
    return {
        user_id: 5,
        character_id: 92004354,
        character_name: 'Naomi Skylar',
        matched_character_name: '',
        blocker: null,
        membership_id: null,
        blocker_date: null,
        ...overrides,
    }
}

describe('invitation labels', () => {
    it('has a status label for every status the API sends', () => {
        const statuses = ['pending', 'accepted', 'declined', 'withdrawn', 'expired']
        expect(statuses.filter((status) => !has_key(`tribes.invite.status.${status}`))).toEqual([])
        expect(invitation_status_label('accepted', t)).toBe('Joined')
    })

    it('has a reason for every blocker the API sends', () => {
        const blockers = ['member', 'applied', 'invited', 'declined_recently', 'on_trial', 'not_eligible']
        expect(blockers.filter((blocker) => !has_key(`tribes.invite.blocker.${blocker}`))).toEqual([])
    })

    it('colors waiting as attention, joined as good, the rest muted', () => {
        expect(invitation_tone('pending')).toBe('attention')
        expect(invitation_tone('accepted')).toBe('good')
        expect(invitation_tone('declined')).toBe('muted')
    })
})

describe('invitation_detail', () => {
    it('shows the DM state and expiry while waiting', () => {
        expect(invitation_detail(invitation(), t, 'en').text).toBe('DM delivered · expires Nov 6')
    })

    it('flags a DM that never landed', () => {
        const skipped = invitation({ dm_status: 'skipped', dm_error: 'No Discord link' })
        expect(invitation_dm_undelivered(skipped)).toBe(true)
        expect(invitation_detail(skipped, t, 'en')).toEqual({
            text: 'DM not delivered: no Discord linked',
            tone: 'attention',
        })
        const closed = invitation({ dm_status: 'skipped', dm_error: 'Discord DM forbidden (403)' })
        expect(invitation_detail(closed, t, 'en').text).toBe('DM not delivered: their DMs are closed')
    })

    it('says when a pilot joined and with how many characters', () => {
        const joined = invitation({ status: 'accepted', responded_at: '2026-10-22T10:00:00Z', joined_character_count: 2 })
        expect(invitation_detail(joined, t, 'en').text).toBe('Joined Oct 22 with 2 characters')
        expect(invitation_dm_undelivered({ ...joined, dm_status: 'skipped' })).toBe(false)
    })

    it('says when a declined pilot can be invited again', () => {
        const declined = invitation({ status: 'declined', responded_at: '2026-10-20T10:00:00Z' })
        expect(invitation_detail(declined, t, 'en').text).toBe('Declined Oct 20 · re-invite from Nov 19')
    })
})

describe('candidate_reason', () => {
    it('explains each blocker with the group and date', () => {
        expect(candidate_reason(candidate(), 'Dreads', t, 'en')).toBe('Can be invited')
        expect(candidate_reason(candidate({ blocker: 'applied', blocker_date: '2026-10-21T08:00:00Z' }), 'Dreads', t, 'en'))
            .toBe('Applied to Dreads Oct 21')
        expect(candidate_reason(candidate({ blocker: 'on_trial' }), 'Dreads', t, 'en'))
            .toBe('On trial. Dreads takes pilots who are off trial.')
    })
})

describe('open_invitation_for_group', () => {
    it('finds the waiting invite to this group only', () => {
        const invites = [
            invitation({ id: 1, tribe_group_id: 2 }),
            invitation({ id: 2, tribe_group_id: 1, status: 'declined' }),
            invitation({ id: 3, tribe_group_id: 1 }),
        ]
        expect(open_invitation_for_group(invites, 1)?.id).toBe(3)
        expect(open_invitation_for_group(invites, 9)).toBeNull()
    })
})
