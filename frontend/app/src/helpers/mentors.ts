import { query_string } from '@helpers/string'
import { eve_clock, eve_day_short } from '@helpers/date'

export const MENTORS_PATH = '/learning/mentors/'
export const MENTEES_PATH = '/learning/mentors/mentees/'
export const MENTOR_SETTINGS_PATH = '/learning/mentors/settings/'
export const MENTORS_ADMIN_PATH = '/learning/mentors/admin/'
export const MENTORS_METRICS_PATH = '/learning/mentors/metrics/'
export const mentor_class_path = (slug: string) => `/learning/mentors/classes/${encodeURIComponent(slug)}/`
export const mentor_class_edit_path = (id: number) => `/learning/mentors/classes/${id}/edit/`
export const NEW_MENTOR_CLASS_PATH = '/learning/mentors/classes/new/'

/** The class page background when a learning manager didn't pick one. */
export const MENTOR_CLASS_DEFAULT_COVER = '/images/guides-cover.jpg'

/** A class's background: its picked cover, or the Learning Center one. */
export function mentor_class_cover(cover_image_url: string | null | undefined): string {
    return cover_image_url || MENTOR_CLASS_DEFAULT_COVER
}

export const MENTORS_HOME_PARTIAL = '/partials/mentors_home_component'
export const MENTORS_MENTEES_PARTIAL = '/partials/mentors_mentees_component'
export const MENTORS_SETTINGS_PARTIAL = '/partials/mentors_settings_component'
export const MENTORS_ADMIN_PARTIAL = '/partials/mentors_admin_component'
export const MENTORS_METRICS_PARTIAL = '/partials/mentors_metrics_component'
export const MENTOR_CLASS_PARTIAL = '/partials/mentor_class_component'
export const MENTOR_CLASS_EDITOR_PARTIAL = '/partials/mentor_class_editor_component'
export const MENTOR_REQUEST_MODAL = '/partials/mentor_request_modal_component'
export const MENTOR_ACCEPT_MODAL = '/partials/mentor_accept_modal_component'
export const MENTOR_FEEDBACK_MODAL = '/partials/mentor_feedback_modal_component'

/** A partial URL with its query, for hx-get / hx-post and show_modal. */
export function mentors_url(base: string, params: Record<string, string | number | undefined>): string {
    const defined = Object.fromEntries(
        Object.entries(params)
            .filter(([, value]) => value !== undefined && value !== '')
            .map(([key, value]) => [key, String(value)])
    )
    const query = query_string(defined)
    return query ? `${base}?${query}` : base
}

/** The bracket chips pilots and mentors pick from, with their EVE hours in winter. */
export const BRACKETS = [
    { code: 'USTZ', hours: '23:00–04:00' },
    { code: 'USTZ+', hours: '04:00–08:00' },
    { code: 'EUTZ', hours: '17:00–22:00' },
    { code: 'EUTZ+', hours: '22:00–02:00' },
    { code: 'AUTZ', hours: '07:00–12:00' },
    { code: 'AUTZ+', hours: '12:00–16:00' },
] as const

export const WEEKDAYS = [0, 1, 2, 3, 4] as const
export const WEEKEND = [5, 6] as const

/** The brackets as "USTZ · USTZ+", or an em dash. */
export function brackets_text(codes: string[]): string {
    return codes.length ? codes.join(' · ') : '—'
}

/** Form values to a list of whole numbers. */
export function form_numbers(values: FormDataEntryValue[]): number[] {
    return values.map(value => parseInt(value as string)).filter(value => !isNaN(value))
}

export function form_strings(values: FormDataEntryValue[]): string[] {
    return values.map(value => String(value)).filter(Boolean)
}

/** "Thu, Nov 13 · 21:00 EVE" for a class time. */
export function class_time(locale: string, iso: string): string {
    return `${eve_day_short(locale, iso, { weekday: true })} · ${eve_clock(iso)} EVE`
}

/** The show_modal call for an Alpine x-on:click. */
export function modal_click(url: string): string {
    return `show_modal({ partial: '${url}' })`
}
