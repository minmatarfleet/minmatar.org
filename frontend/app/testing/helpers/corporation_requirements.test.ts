import { expect, test } from 'vitest'

import {
    apply_state,
    blocking_checks,
    form_values,
    group_by_importance,
    over_asks,
    parse_prime_time,
    requirement_from_form,
    rules_as_checks,
} from '@helpers/corporations/requirements'

const check = (importance: string, status: string) => ({
    id: 1, kind: 'ships', importance, text: 'Fly', status,
    detail: '', ship_type_ids: [], training_days: null,
})

test('groups required and preferred', () => {
    const groups = group_by_importance([check('required', 'met'), check('preferred', 'unmet')])
    expect(groups.required).toHaveLength(1)
    expect(groups.preferred).toHaveLength(1)
})

test('only unmet or training required rules block', () => {
    expect(blocking_checks([
        check('required', 'unknown'),
        check('required', 'met'),
        check('preferred', 'unmet'),
    ])).toHaveLength(0)
    expect(blocking_checks([check('required', 'training')])).toHaveLength(1)
})

test('apply state', () => {
    expect(apply_state(false, true)).toBe('signed_out')
    expect(apply_state(true, true)).toBe('ready')
    expect(apply_state(true, false)).toBe('blocked')
})

test('prime time lines parse with or without a range', () => {
    expect(parse_prime_time('EUTZ (16:00 - 20:00)')).toMatchObject({
        label: 'EUTZ', eve_range: '16:00–20:00', start_minutes: 960, end_minutes: 1200,
    })
    expect(parse_prime_time('Weekends')).toMatchObject({ label: 'Weekends', eve_range: null })
})

test('form parsing per kind', () => {
    const form = new FormData()
    form.set('kind', 'ships')
    form.set('target', 'capability')
    form.set('capability', 'Dreads')
    form.set('who', 'other_account')
    form.set('importance', 'required')
    expect(requirement_from_form(form)).toEqual({
        kind: 'ships',
        params: { target: 'capability', capability: 'Dreads', level: 'can_fly' },
        who: 'other_account',
        importance: 'required',
    })

    const sp = new FormData()
    sp.set('kind', 'skill_points')
    sp.set('minimum_millions', '20')
    expect(requirement_from_form(sp).params).toEqual({ minimum: 20_000_000 })

    const tz = new FormData()
    tz.set('kind', 'prime_time')
    tz.append('brackets', 'EUTZ')
    tz.append('brackets', 'USTZ')
    expect(requirement_from_form(tz)).toMatchObject({ params: { brackets: ['EUTZ', 'USTZ'] }, importance: 'preferred' })
})

test('form values prefill from a rule', () => {
    expect(form_values({ kind: 'skill_points', params: { minimum: 30_000_000 }, who: 'main', importance: 'required' }))
        .toMatchObject({ kind: 'skill_points', minimum_millions: 30, who: 'main' })
    expect(form_values(null)).toMatchObject({ kind: 'ships', importance: 'preferred' })
})

test('signed-out rules read as unknown checks', () => {
    const [only] = rules_as_checks([{ id: 3, kind: 'kills', params: {}, who: 'any', importance: 'required', position: 0, text: 'Kills' }])
    expect(only).toMatchObject({ id: 3, status: 'unknown', text: 'Kills' })
})

test('over-asking required rules', () => {
    expect(over_asks({ importance: 'required', members_pass: 41 })).toBe(true)
    expect(over_asks({ importance: 'preferred', members_pass: 10 })).toBe(false)
    expect(over_asks({ importance: 'required', members_pass: null })).toBe(false)
})

test('prime time lines split on newlines', async () => {
    const { prime_time_lines } = await import('@helpers/corporations/requirements')
    expect(prime_time_lines(['AUTZ (10:00 - 13:00)\r\nEUTZ (16:00 - 20:00)', ' USTZ '])).toEqual([
        'AUTZ (10:00 - 13:00)', 'EUTZ (16:00 - 20:00)', 'USTZ',
    ])
})

test('training toward a nice-to-have reads neutral', async () => {
    const { check_tone } = await import('@helpers/corporations/requirements')
    expect(check_tone({ status: 'training', importance: 'preferred' })).toBe('unmet')
    expect(check_tone({ status: 'training', importance: 'required' })).toBe('training')
})
