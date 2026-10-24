/**
 * Copy this fleet: the dialog's default date, the start time it posts, and
 * the alert the new fleet's page shows (see backend fleets/helpers/copy_fleet.py).
 */
import { eve_clock, eve_day } from '@helpers/date'
import { t_key } from '@helpers/i18n'

const WEEK_MS = 7 * 24 * 60 * 60 * 1000

/** Settings the backend can leave off a copy, in the order the alert lists them. */
export const NOT_COPIED_KEYS = ['campaign', 'location', 'open_to_alliance'] as const
export type NotCopied = typeof NOT_COPIED_KEYS[number]

/**
 * The same EVE weekday and time as the fleet, one week on; further weeks on
 * when that has already passed (a fleet copied a month later).
 */
export function copy_default_start(start_time:string, now:Date = new Date()):{ eve_date: string, eve_time: string } {
    let start = new Date(start_time).getTime() + WEEK_MS
    while (start <= now.getTime())
        start += WEEK_MS

    return { eve_date: eve_day(start), eve_time: eve_clock(start) }
}

/** The ISO start time for an EVE date (YYYY-MM-DD) and time (HH:MM), or null. */
export function copy_start_iso(eve_date:string, eve_time:string):string | null {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(eve_date) || !/^\d{2}:\d{2}$/.test(eve_time))
        return null

    const start = new Date(`${eve_date}T${eve_time}:00Z`)
    return isNaN(start.getTime()) ? null : start.toISOString()
}

/** The `not_copied` query value, known keys only. */
export function parse_not_copied(value:string | null | undefined):NotCopied[] {
    const given = new Set((value ?? '').split(',').map(key => key.trim()))
    return NOT_COPIED_KEYS.filter(key => given.has(key))
}

/** The new fleet's page URL with the copy alert's query. */
export function copied_fleet_path(fleet_id:number, copied_from:number, not_copied:string[]):string {
    const query = new URLSearchParams({ copied_from: String(copied_from) })
    const known = parse_not_copied(not_copied.join(','))
    if (known.length > 0)
        query.set('not_copied', known.join(','))

    return `/fleets/upcoming/${fleet_id}?${query.toString()}`
}

type Translate = (key:string) => string

/** The alert's HTML: what was copied, then one line per setting left off. */
export function copied_alert_content(not_copied:NotCopied[], t:Translate):string {
    const lines = [`<p>${t('fleets.copy.copied_text')}</p>`]
    if (not_copied.length > 0) {
        lines.push(`<p>${t('fleets.copy.not_copied')}</p>`)
        lines.push(`<ul>${not_copied.map(key => `<li>${t(t_key('fleets.copy.not_copied.', key))}</li>`).join('')}</ul>`)
    }
    return lines.join('')
}
