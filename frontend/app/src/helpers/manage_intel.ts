/**
 * Small formatting and filtering helpers for the intel manage screens:
 * structure timers (/intel/timers/manage/) and NPSI calendar feeds
 * (/fleets/npsi-sources/).
 */
import type { StructureTimer } from '@dtypes/api.minmatar.org'

/** A backend date-time, which may arrive without a zone (naive = UTC). */
export function parse_iso(iso: string | null | undefined): Date | null {
    if (!iso) return null
    const zoned = /([zZ]|[+-]\d\d:?\d\d)$/.test(iso) ? iso : `${iso}Z`
    const date = new Date(zoned)
    return Number.isNaN(date.getTime()) ? null : date
}

/** "Sun 08 Nov 22:26" in EVE time (UTC). */
export function eve_day_time(iso: string | null | undefined, lang: string): string {
    const date = parse_iso(iso)
    if (!date) return ''
    const weekday = date.toLocaleDateString(lang, { weekday: 'short', timeZone: 'UTC' })
    const month = date.toLocaleDateString(lang, { month: 'short', timeZone: 'UTC' })
    const day = String(date.getUTCDate()).padStart(2, '0')
    return `${weekday} ${day} ${month} ${date.toISOString().slice(11, 16)}`
}

/** "HH:MM" EVE time when today, "08 Nov HH:MM" otherwise. */
export function eve_short_day_time(iso: string | null | undefined, lang: string, now: Date = new Date()): string {
    const date = parse_iso(iso)
    if (!date) return ''
    const time = date.toISOString().slice(11, 16)
    if (date.toISOString().slice(0, 10) === now.toISOString().slice(0, 10)) return time
    const month = date.toLocaleDateString(lang, { month: 'short', timeZone: 'UTC' })
    return `${String(date.getUTCDate()).padStart(2, '0')} ${month} ${time}`
}

export interface CountdownParts {
    future:     boolean;
    days:       number;
    hours:      number;
    minutes:    number;
}

/** How far a time is from now, in days, hours and minutes. */
export function countdown_parts(iso: string | null | undefined, now: Date = new Date()): CountdownParts | null {
    const date = parse_iso(iso)
    if (!date) return null
    const ms = date.getTime() - now.getTime()
    const total_minutes = Math.floor(Math.abs(ms) / 60_000)
    return {
        future: ms >= 0,
        days: Math.floor(total_minutes / 1440),
        hours: Math.floor((total_minutes % 1440) / 60),
        minutes: total_minutes % 60,
    }
}

export type TimerView = 'upcoming' | 'past'

export const TIMER_VIEWS: TimerView[] = ['upcoming', 'past']

const WEEK_MS = 7 * 24 * 3_600_000

/** Does the timer belong in a view: upcoming, or due in the past 7 days. */
export function timer_in_view(timer: StructureTimer, view: TimerView, now: Date = new Date()): boolean {
    const when = parse_iso(timer.timer)?.getTime()
    if (when === undefined) return false
    if (view === 'upcoming') return when >= now.getTime()
    return when < now.getTime() && when >= now.getTime() - WEEK_MS
}

/** Search across system, structure name and owner (corporation or alliance). */
export function timer_matches(timer: StructureTimer, query: string): boolean {
    const needle = query.trim().toLowerCase()
    if (!needle) return true
    return [timer.system_name, timer.name, timer.corporation_name, timer.alliance_name]
        .some((value) => (value ?? '').toLowerCase().includes(needle))
}

/** Upcoming soonest first; the past week most recent first. */
export function sort_timers(timers: StructureTimer[], view: TimerView): StructureTimer[] {
    const time = (timer: StructureTimer) => parse_iso(timer.timer)?.getTime() ?? 0
    return [...timers].sort((a, b) => view === 'upcoming' ? time(a) - time(b) : time(b) - time(a))
}

/** The owner shown in the list: the alliance when known, else the corporation. */
export function timer_owner(timer: StructureTimer): string | null {
    return timer.alliance_name || timer.corporation_name || null
}

/** "StructureUnderAttack" -> "Structure under attack". */
export function notification_label(notification_type: string): string {
    const words = notification_type.replace(/([a-z0-9])([A-Z])/g, '$1 $2').toLowerCase()
    return words.charAt(0).toUpperCase() + words.slice(1)
}

/** The <tbody> id of a timer's row: what its saves and deletes swap. */
export const timer_row_id = (id: number) => `timer-row-${id}`

/** The <tbody> id of a feed's row. */
export const feed_row_id = (id: number | 'new') => `npsi-row-${id}`

/** What was typed into the new-feed row, shown again with its error. */
export interface NpsiFeedDraft {
    name:                   string;
    feed_url:               string;
    fc_character_name:      string;
    fc_character_id:        string;
    default_audience_id:    string;
}

export type NpsiFeedView = 'all' | 'on' | 'failing'
