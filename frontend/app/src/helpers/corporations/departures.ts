import type { DepartureAnswer, DepartureGroup, HistoryEntry } from '@dtypes/api.minmatar.org'

export type DepartureTag = 'npc' | 'exit' | 'alliance_move'
export type DepartureReason = 'kicked_inactive' | 'kicked_other' | 'left'

export const DEPARTURE_REASONS: DepartureReason[] = ['kicked_inactive', 'kicked_other', 'left']
const KICKS: string[] = ['kicked_inactive', 'kicked_other']

export interface DepartureRowView {
    tag: DepartureTag
    answered: boolean
    shows_can_rejoin: boolean
    /** The value posted for this row's checkbox: one person, alts included. */
    row_value: string
}

export function departure_row_view(group: DepartureGroup): DepartureRowView {
    const tag: DepartureTag = group.destination_is_npc
        ? 'npc'
        : group.kind === 'alliance_move' ? 'alliance_move' : 'exit'
    return {
        tag,
        answered: group.reason !== '',
        shows_can_rejoin: KICKS.includes(group.reason),
        row_value: group.departure_ids.join(','),
    }
}

/** The answer form: ticked rows (each "1,2" for a person and their alts) and one choice. */
export function parse_departure_answer(form: FormData): DepartureAnswer | null {
    const reason = String(form.get('reason') ?? '')
    if (!(DEPARTURE_REASONS as string[]).includes(reason)) return null
    const departure_ids = form.getAll('rows')
        .flatMap((value) => String(value).split(','))
        .map((value) => parseInt(value, 10))
        .filter((value) => Number.isInteger(value) && value > 0)
    const choice = String(form.get('can_rejoin') ?? '')
    const can_rejoin = KICKS.includes(reason) && (choice === 'yes' || choice === 'no')
        ? choice === 'yes'
        : null
    return {
        departure_ids,
        reason,
        can_rejoin,
        note: String(form.get('note') ?? '').trim(),
    }
}

export type HistoryTag = 'cant_rejoin' | 'inactive_kick' | 'other_kick' | 'left'

/** The tag a recruiter sees on one history entry: a flag beats the reason. */
export function history_tag(entry: HistoryEntry): HistoryTag {
    if (entry.flag_active) return 'cant_rejoin'
    if (entry.reason === 'kicked_inactive') return 'inactive_kick'
    if (entry.reason === 'kicked_other') return 'other_kick'
    return 'left'
}

export function has_active_flag(history: HistoryEntry[] | null | undefined): boolean {
    return (history ?? []).some((entry) => entry.flag_active)
}
