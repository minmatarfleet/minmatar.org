/**
 * The tribe event form: recurrence labels and the request bodies it sends
 * (docs/tribes/tribe-publishing.md, Events). Times are EVE time (UTC).
 */
import type {
    TribeEvent,
    TribeEventCreate,
    TribeEventPatch,
    TribeEventRecurrence,
} from '@dtypes/api.minmatar.org'
import { eve_clock, eve_day } from '@helpers/date'

const WEEKDAYS = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
const ORDINALS = ['1st', '2nd', '3rd', '4th', '5th']

/** Which occurrence of its weekday in the month (1-5), as the backend repeats monthly events. */
export function nth_weekday(date: Date): number {
    return Math.floor((date.getUTCDate() - 1) / 7) + 1
}

export interface RecurrenceLabelTemplates {
    none:       string;
    /** `{weekday}` */
    weekly:     string;
    /** `{nth}` and `{weekday}` */
    monthly:    string;
}

/** The three choices of the Repeats select, worded for the chosen start day. */
export function recurrence_labels(starts: Date | null, templates: RecurrenceLabelTemplates): Record<TribeEventRecurrence, string> {
    const valid = starts && !Number.isNaN(starts.getTime())
    const weekday = valid ? WEEKDAYS[starts.getUTCDay()] : ''
    const nth = valid ? ORDINALS[nth_weekday(starts) - 1] : ''
    const fill = (template: string) => template
        .replace('{weekday}', weekday)
        .replace('{nth}', nth)
        .replace(/,\s*$/, '')
        .replace(/\s+/g, ' ')
        .trim()
    return {
        none: templates.none,
        weekly: fill(templates.weekly),
        monthly: fill(templates.monthly),
    }
}

/** `YYYY-MM-DD` + `HH:MM` in EVE time as an ISO string, or null when either is missing or invalid. */
export function eve_iso(date: string, time: string): string | null {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(date) || !/^\d{2}:\d{2}$/.test(time)) return null
    const moment = new Date(`${date}T${time}:00Z`)
    return Number.isNaN(moment.getTime()) ? null : moment.toISOString()
}

/**
 * The end from an end time on the start's day; an end at or before the start
 * means the event runs past midnight EVE.
 */
export function ends_iso(starts_at: string | null, end_time: string): string | null {
    if (!starts_at || !end_time) return null
    const ends = eve_iso(eve_day(starts_at), end_time)
    if (!ends) return null
    const moment = new Date(ends)
    if (moment.getTime() <= new Date(starts_at).getTime())
        moment.setUTCDate(moment.getUTCDate() + 1)
    return moment.toISOString()
}

const RECURRENCES: TribeEventRecurrence[] = ['none', 'weekly', 'monthly']

interface FormValues {
    get(name: string): FormDataEntryValue | null;
}

const text = (form: FormValues, name: string) => String(form.get(name) ?? '').trim()

/**
 * The create body from the form fields: title, description, eve_date,
 * eve_time, end_time, recurrence, where_kind, voice_channel_id, location,
 * members_only, announce (checkboxes send "on"). Members only is dropped for a
 * location, which Discord shows to the whole server. `starts_at` is '' when
 * the date or time is missing, so the API rejects it with its own message.
 *
 * Discord ids stay strings: snowflakes don't fit a JavaScript number, and the
 * API takes digit strings (the schema only says number).
 */
export function event_create_body(form: FormValues): TribeEventCreate {
    const starts_at = eve_iso(text(form, 'eve_date'), text(form, 'eve_time'))
    const where_kind = text(form, 'where_kind') === 'place' ? 'place' : 'voice'
    const recurrence = RECURRENCES.find((value) => value === text(form, 'recurrence')) ?? 'none'
    const voice_channel_id = where_kind === 'voice' ? text(form, 'voice_channel_id') : ''

    return {
        title: text(form, 'title'),
        description: text(form, 'description'),
        starts_at: starts_at ?? '',
        ends_at: ends_iso(starts_at, text(form, 'end_time')),
        recurrence,
        where_kind,
        voice_channel_id: (voice_channel_id || null) as unknown as number | null,
        location: where_kind === 'place' ? text(form, 'location') : '',
        members_only: where_kind === 'voice' && form.get('members_only') === 'on',
        announce: form.get('announce') === 'on',
    }
}

/** An edit sends every field it shows (announce only applies when the event is created). */
export function event_patch_body(form: FormValues): TribeEventPatch {
    const { announce: _announce, ...body } = event_create_body(form)
    return body
}

export interface EventFormValues {
    title:              string;
    description:        string;
    eve_date:           string;
    eve_time:           string;
    end_time:           string;
    recurrence:         TribeEventRecurrence;
    where_kind:         'voice' | 'place';
    voice_channel_id:   string;
    location:           string;
    members_only:       boolean;
    announce:           boolean;
}

/** The form's starting values: an event being edited, or a new one starting at `default_start`. */
export function event_form_values(event: TribeEvent | null, default_start: Date): EventFormValues {
    if (!event) {
        return {
            title: '',
            description: '',
            eve_date: eve_day(default_start),
            eve_time: eve_clock(default_start),
            end_time: '',
            recurrence: 'none',
            where_kind: 'voice',
            voice_channel_id: '',
            location: '',
            members_only: false,
            announce: true,
        }
    }
    return {
        title: event.title,
        description: event.description,
        eve_date: eve_day(event.starts_at),
        eve_time: eve_clock(event.starts_at),
        end_time: event.ends_at ? eve_clock(event.ends_at) : '',
        recurrence: event.recurrence,
        where_kind: event.where_kind === 'place' ? 'place' : 'voice',
        voice_channel_id: event.voice_channel_id ?? '',
        location: event.location ?? '',
        members_only: event.members_only,
        announce: event.announce,
    }
}

/** The fields as submitted, to show the form again after a failed save. */
export function event_form_values_from_form(form: FormValues): EventFormValues {
    const recurrence = RECURRENCES.find((value) => value === text(form, 'recurrence')) ?? 'none'
    return {
        title: text(form, 'title'),
        description: text(form, 'description'),
        eve_date: text(form, 'eve_date'),
        eve_time: text(form, 'eve_time'),
        end_time: text(form, 'end_time'),
        recurrence,
        where_kind: text(form, 'where_kind') === 'place' ? 'place' : 'voice',
        voice_channel_id: text(form, 'voice_channel_id'),
        location: text(form, 'location'),
        members_only: form.get('members_only') === 'on',
        announce: form.get('announce') === 'on',
    }
}

/** A new event's default start: the next whole hour at least an hour away. */
export function default_event_start(now: Date = new Date()): Date {
    const start = new Date(now.getTime() + 60 * 60 * 1000)
    if (start.getUTCMinutes() > 0 || start.getUTCSeconds() > 0 || start.getUTCMilliseconds() > 0) {
        start.setUTCHours(start.getUTCHours() + 1, 0, 0, 0)
    }
    return start
}
