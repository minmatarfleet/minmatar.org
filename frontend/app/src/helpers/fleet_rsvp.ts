/**
 * The fleet invite sign-up page (/fleets/rsvp/<token>/): the pilot pressed
 * I'm available in Discord and the bot DMed them a 10-minute link. These are
 * the pure bits the page, its partial and the tests share.
 */
import type { RsvpCharacter, RsvpSubmit } from '@dtypes/api.minmatar.org'
import { get_player_icon, get_type_icon } from '@helpers/eve_image'

export const RSVP_CONFIDENCES = ['high', 'medium', 'low'] as const
export type RsvpConfidence = typeof RSVP_CONFIDENCES[number]

/** What the form's submit buttons send as `intent`. */
export type RsvpIntent = 'sign_up' | 'not_available'

/**
 * A Django signed token: base64url, `:` separators and a leading `.` when
 * compressed. Anything else never reaches the API (no `/`, no `..` segment).
 */
export function is_rsvp_token(token: string | undefined | null): token is string {
    return typeof token === 'string' && /^[\w\-.:]{20,1000}$/.test(token)
}

export function rsvp_confidence(value: unknown): RsvpConfidence {
    return RSVP_CONFIDENCES.includes(value as RsvpConfidence) ? value as RsvpConfidence : 'high'
}

/** The fit a ticked row starts on: what they picked, else their usual, else the first. */
export function default_fit_key(character: Pick<RsvpCharacter, 'fits' | 'picked_key' | 'suggested_key'>): string {
    const keys = character.fits.map((fit) => fit.key)
    if (character.picked_key && keys.includes(character.picked_key)) return character.picked_key
    if (character.suggested_key && keys.includes(character.suggested_key)) return character.suggested_key
    return keys[0] ?? ''
}

/** `f:12` is a catalog fitting, `m:34` a fleet-only fitting (see backend invite_rsvp._key). */
export function parse_fit_key(key: string): { fitting_id: number } | { fleet_fitting_id: number } | null {
    const match = /^([fm]):(\d+)$/.exec(key)
    if (!match) return null
    const id = Number(match[2])
    return match[1] === 'f' ? { fitting_id: id } : { fleet_fitting_id: id }
}

/**
 * The POST body from the submitted form: each ticked `character` with the
 * ship in its `fit_<id>` select. A ticked character with no fit (a fleet
 * with no doctrine) adds no pick: no picks signs up with no ship yet.
 */
export function rsvp_submit_from_form(data: FormData): RsvpSubmit {
    const seen = new Set<number>()
    const picks: RsvpSubmit['picks'] = []
    for (const value of data.getAll('character')) {
        const character_id = Number(value)
        if (!Number.isInteger(character_id) || character_id <= 0 || seen.has(character_id)) continue
        seen.add(character_id)
        const fit = parse_fit_key(String(data.get(`fit_${character_id}`) ?? ''))
        if (fit) picks.push({ character_id, ...fit })
    }
    return { picks, confidence: rsvp_confidence(data.get('confidence')) }
}

export function rsvp_intent(data: FormData): RsvpIntent {
    return data.get('intent') === 'not_available' ? 'not_available' : 'sign_up'
}

/** "19:00 EVE · Fri 13 Nov": EVE (UTC) clock, then the EVE day. */
export function eve_when_text(start_time: string | Date, template = '{time} EVE · {day}'): string {
    const date = new Date(start_time)
    const time = date.toISOString().slice(11, 16)
    const day = date.toLocaleDateString('en-GB', { weekday: 'short', day: 'numeric', month: 'short', timeZone: 'UTC' }).replace(',', '')
    return template.replace('{time}', time).replace('{day}', day)
}

export interface CountdownTemplates {
    days:       string;
    hours:      string;
    minutes:    string;
    started:    string;
}

/**
 * "in 2h 48m" from milliseconds until the start. The page's Alpine ticker
 * repeats this formula in the browser (FleetRsvpWhen.astro).
 */
export function countdown_text(templates: CountdownTemplates, ms: number): string {
    if (!(ms > 0)) return templates.started
    const total = Math.floor(ms / 60000)
    const d = Math.floor(total / 1440)
    const h = Math.floor((total % 1440) / 60)
    const m = total % 60
    if (d > 0) return templates.days.replace('{d}', String(d)).replace('{h}', String(h))
    if (h > 0) return templates.hours.replace('{h}', String(h)).replace('{m}', String(m))
    return templates.minutes.replace('{m}', String(m))
}

/** Portrait and ship icon URLs on the EVE image server. */
export const rsvp_portrait = (character_id: number | null | undefined, size = 64) =>
    get_player_icon(character_id ?? 1, size)

export const rsvp_ship_icon = (ship_id: number | null | undefined, size = 64) =>
    get_type_icon(ship_id ?? 0, size)

/** Where "Back to Discord" goes: the pilot's DMs, where the invite is. */
export const DISCORD_DMS_URL = 'https://discord.com/channels/@me'
