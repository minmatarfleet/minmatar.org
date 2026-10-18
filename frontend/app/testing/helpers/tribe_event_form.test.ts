import { describe, expect, it } from 'vitest'
import type { TribeEvent } from '@dtypes/api.minmatar.org'
import {
    default_event_start,
    ends_iso,
    eve_iso,
    event_create_body,
    event_form_values,
    event_form_values_from_form,
    event_patch_body,
    nth_weekday,
    recurrence_labels,
} from '@helpers/tribe_event_form'

const templates = {
    none: 'Does not repeat',
    weekly: 'Weekly, {weekday}',
    monthly: 'Monthly, {nth} {weekday}',
}

const form = (fields: Record<string, string>) => {
    const data = new FormData()
    Object.entries(fields).forEach(([name, value]) => data.append(name, value))
    return data
}

describe('event recurrence labels', () => {
    it('names the nth weekday of the month', () => {
        expect(nth_weekday(new Date('2026-11-14T19:00:00Z'))).toBe(2)
        expect(nth_weekday(new Date('2026-11-01T19:00:00Z'))).toBe(1)
        expect(nth_weekday(new Date('2026-10-31T19:00:00Z'))).toBe(5)
    })

    it('words the Repeats choices for the start day', () => {
        expect(recurrence_labels(new Date('2026-11-14T19:00:00Z'), templates)).toEqual({
            none: 'Does not repeat',
            weekly: 'Weekly, Saturday',
            monthly: 'Monthly, 2nd Saturday',
        })
    })

    it('uses the EVE (UTC) day, not the viewer\'s', () => {
        expect(recurrence_labels(new Date('2026-11-14T23:30:00Z'), templates).weekly).toBe('Weekly, Saturday')
    })

    it('drops the day when there is no valid start', () => {
        expect(recurrence_labels(null, templates)).toEqual({ none: 'Does not repeat', weekly: 'Weekly', monthly: 'Monthly' })
        expect(recurrence_labels(new Date('nope'), templates).monthly).toBe('Monthly')
    })
})

describe('event times', () => {
    it('reads date and time as EVE time', () => {
        expect(eve_iso('2026-11-14', '19:00')).toBe('2026-11-14T19:00:00.000Z')
        expect(eve_iso('2026-11-14', '')).toBeNull()
        expect(eve_iso('14/11/2026', '19:00')).toBeNull()
    })

    it('ends on the start day, or the next one past midnight', () => {
        expect(ends_iso('2026-11-14T19:00:00.000Z', '20:30')).toBe('2026-11-14T20:30:00.000Z')
        expect(ends_iso('2026-11-14T23:00:00.000Z', '01:00')).toBe('2026-11-15T01:00:00.000Z')
        expect(ends_iso('2026-11-14T19:00:00.000Z', '')).toBeNull()
        expect(ends_iso(null, '20:00')).toBeNull()
    })

    it('starts a new event on a whole hour at least an hour out', () => {
        expect(default_event_start(new Date('2026-10-18T10:20:00Z')).toISOString()).toBe('2026-10-18T12:00:00.000Z')
        expect(default_event_start(new Date('2026-10-18T10:00:00Z')).toISOString()).toBe('2026-10-18T11:00:00.000Z')
    })
})

describe('event request bodies', () => {
    const voice = {
        title: ' Town Hall #38 ',
        description: 'Leadership updates.',
        eve_date: '2026-11-14',
        eve_time: '19:00',
        end_time: '20:30',
        recurrence: 'monthly',
        where_kind: 'voice',
        voice_channel_id: '1172908092573360149',
        members_only: 'on',
        announce: 'on',
    }

    it('builds the create body, keeping the Discord id a string', () => {
        expect(event_create_body(form(voice))).toEqual({
            title: 'Town Hall #38',
            description: 'Leadership updates.',
            starts_at: '2026-11-14T19:00:00.000Z',
            ends_at: '2026-11-14T20:30:00.000Z',
            recurrence: 'monthly',
            where_kind: 'voice',
            voice_channel_id: '1172908092573360149',
            location: '',
            members_only: true,
            announce: true,
        })
    })

    it('never makes a location event members only, and drops the channel', () => {
        const body = event_create_body(form({
            ...voice,
            where_kind: 'place',
            location: 'Reykjavik',
        }))
        expect(body.where_kind).toBe('place')
        expect(body.location).toBe('Reykjavik')
        expect(body.voice_channel_id).toBeNull()
        expect(body.members_only).toBe(false)
    })

    it('falls back to no repeat and leaves a missing start for the API to reject', () => {
        const body = event_create_body(form({ title: 'x', recurrence: 'daily', eve_date: '', eve_time: '' }))
        expect(body.recurrence).toBe('none')
        expect(body.starts_at).toBe('')
        expect(body.ends_at).toBeNull()
        expect(body.announce).toBe(false)
    })

    it('leaves announce out of an edit', () => {
        const patch = event_patch_body(form(voice))
        expect(patch).not.toHaveProperty('announce')
        expect(patch.title).toBe('Town Hall #38')
    })

    it('shows the submitted fields again after a failed save', () => {
        expect(event_form_values_from_form(form(voice))).toMatchObject({
            title: 'Town Hall #38',
            eve_date: '2026-11-14',
            end_time: '20:30',
            recurrence: 'monthly',
            voice_channel_id: '1172908092573360149',
            members_only: true,
            announce: true,
        })
    })
})

describe('event form values', () => {
    it('starts a new event in voice, announced', () => {
        const values = event_form_values(null, new Date('2026-10-18T12:00:00Z'))
        expect(values).toMatchObject({ eve_date: '2026-10-18', eve_time: '12:00', where_kind: 'voice', announce: true, recurrence: 'none' })
    })

    it('fills an edit from the event', () => {
        const event = {
            title: 'Fanfest meetup',
            description: 'Meet the alliance.',
            starts_at: '2027-05-01T18:00:00Z',
            ends_at: '2027-05-01T22:00:00Z',
            recurrence: 'none',
            where_kind: 'place',
            voice_channel_id: null,
            location: 'Reykjavik',
            members_only: false,
            announce: false,
        } as unknown as TribeEvent
        expect(event_form_values(event, new Date())).toEqual({
            title: 'Fanfest meetup',
            description: 'Meet the alliance.',
            eve_date: '2027-05-01',
            eve_time: '18:00',
            end_time: '22:00',
            recurrence: 'none',
            where_kind: 'place',
            voice_channel_id: '',
            location: 'Reykjavik',
            members_only: false,
            announce: false,
        })
    })
})
