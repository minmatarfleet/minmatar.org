import type { TribeInvitation, TribeInvitationCandidate } from '@dtypes/api.minmatar.org'
import { eve_day_short } from '@helpers/date'
import { t_key, type TranslationKey } from '@helpers/i18n'

type Translate = (key: TranslationKey) => string

/** red = action, orange = attention, green = good; answered invites are muted. */
export type InvitationTone = 'attention' | 'good' | 'muted' | 'default'

export const REINVITE_WAIT_DAYS = 30

const DAY_MS = 24 * 60 * 60 * 1000

export function invitation_status_label(status: string, t: Translate): string {
    return t(t_key('tribes.invite.status.', status)) ?? status
}

export function invitation_tone(status: string): InvitationTone {
    if (status === 'pending') return 'attention'
    if (status === 'accepted') return 'good'
    return 'muted'
}

/** The DM never landed: no linked Discord, or the pilot's DMs are closed. */
export function invitation_dm_undelivered(invitation: TribeInvitation): boolean {
    return invitation.status === 'pending'
        && (invitation.dm_status === 'skipped' || invitation.dm_status === 'failed')
}

/** One line under the status: DM state and expiry while waiting, otherwise what happened and when. */
export function invitation_detail(invitation: TribeInvitation, t: Translate, lang: string): { text: string, tone: InvitationTone } {
    const day = (value: string) => eve_day_short(lang, value)
    const responded = invitation.responded_at ?? invitation.expires_at

    switch (invitation.status) {
        case 'pending': {
            const expires = day(invitation.expires_at)
            if (invitation_dm_undelivered(invitation)) {
                const no_discord = (invitation.dm_error ?? '').toLowerCase().includes('no discord')
                return {
                    text: t(no_discord ? 'tribes.invite.detail.dm_no_discord' : 'tribes.invite.detail.dm_closed'),
                    tone: 'attention',
                }
            }
            if (invitation.dm_status === null)
                return { text: t('tribes.invite.detail.no_dm').replace('{date}', expires), tone: 'default' }
            const key = invitation.dm_status === 'pending' ? 'tribes.invite.detail.dm_pending' : 'tribes.invite.detail.dm_sent'
            return { text: t(key).replace('{date}', expires), tone: 'default' }
        }
        case 'accepted': {
            const count = invitation.joined_character_count ?? 0
            const text = count > 1
                ? t('tribes.invite.detail.joined_with').replace('{count}', String(count))
                : t('tribes.invite.detail.joined')
            return { text: text.replace('{date}', day(responded)), tone: 'default' }
        }
        case 'declined': {
            const until = new Date(new Date(responded).getTime() + REINVITE_WAIT_DAYS * DAY_MS)
            return {
                text: t('tribes.invite.detail.declined')
                    .replace('{date}', day(responded))
                    .replace('{until}', eve_day_short(lang, until)),
                tone: 'muted',
            }
        }
        case 'withdrawn':
            return { text: t('tribes.invite.detail.withdrawn').replace('{date}', day(responded)), tone: 'muted' }
        default:
            return { text: t('tribes.invite.detail.expired').replace('{date}', day(invitation.expires_at)), tone: 'muted' }
    }
}

/** Why a search result can't be picked, or the "can be invited" line. */
export function candidate_reason(candidate: TribeInvitationCandidate, group_name: string, t: Translate, lang: string): string {
    if (!candidate.blocker) return t('tribes.invite.can_invite')
    const date = candidate.blocker_date ? eve_day_short(lang, candidate.blocker_date) : ''
    return (t(t_key('tribes.invite.blocker.', candidate.blocker)) ?? '')
        .replace('{group}', group_name)
        .replace('{date}', date)
}

/** The pilot's waiting invite to this group, if any. */
export function open_invitation_for_group(invitations: TribeInvitation[], group_id: number): TribeInvitation | null {
    return invitations.find((invitation) => invitation.tribe_group_id === group_id && invitation.status === 'pending') ?? null
}
