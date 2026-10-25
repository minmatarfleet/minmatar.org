/**
 * Invite picks the send will skip: a pilot who already had their one fleet
 * invite this week, or who turned fleet invites off. The FC can still pick
 * them; the chip says Skipped and why (see backend
 * fleets/helpers/private_fleets.py).
 */
import { eve_day_short } from '@helpers/date'
import type { useTranslations } from '@i18n/utils'
import type { FleetInviteCandidate } from '@helpers/api.minmatar.org/fleets'

type Translate = ReturnType<typeof useTranslations>
type InviteBlock = Pick<FleetInviteCandidate, 'blocked' | 'capped'>

/** Blocks that still let the FC add the pick; the send leaves them out. */
export function is_skipped(blocked:string | null | undefined):boolean {
    return blocked === 'capped' || blocked === 'opted_out'
}

/** "Thu, Oct 30" in EVE time. */
export function invite_day(lang:string, date:string):string {
    return eve_day_short(lang, date, { weekday: true })
}

/** Why a skipped pick is skipped, for the chip's hover text; '' when it isn't. */
export function skip_note(t:Translate, lang:string, pick:InviteBlock):string {
    if (pick.blocked === 'opted_out')
        return t('fleets.invites.skip_opted_out')

    if (pick.blocked !== 'capped' || !pick.capped)
        return ''

    return t('fleets.invites.skip_capped')
        .replace('{fleet}', pick.capped.fleet)
        .replace('{day}', invite_day(lang, pick.capped.invited_at))
        .replace('{free}', invite_day(lang, pick.capped.free_at))
}
