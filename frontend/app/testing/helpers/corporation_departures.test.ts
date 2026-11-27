import { expect, test } from 'vitest'
import { departure_row_view, parse_departure_answer } from '@helpers/corporations/departures'
import type { DepartureGroup } from '@dtypes/api.minmatar.org'

function group(fields: Partial<DepartureGroup> = {}): DepartureGroup {
    return {
        departure_ids: [1],
        character_id: 2112000001,
        character_name: 'Arkan Veld',
        alt_names: [],
        registered: true,
        months_in_corporation: 14,
        first_missing_at: '2026-11-20T12:00:00Z',
        destination_corporation_id: 1000167,
        destination_name: 'Pator Tech School',
        kind: 'exit',
        destination_is_npc: true,
        reason: '',
        can_rejoin: null,
        note: '',
        flag_id: null,
        survey_sent_at: null,
        ...fields,
    }
}

test('an NPC destination is tagged NPC corp, not Exit', () => {
    expect(departure_row_view(group()).tag).toBe('npc')
    expect(departure_row_view(group({ destination_is_npc: false })).tag).toBe('exit')
    expect(departure_row_view(group({ kind: 'alliance_move', destination_is_npc: false })).tag).toBe('alliance_move')
})

test('can rejoin shows for kicks only', () => {
    expect(departure_row_view(group({ reason: 'kicked_inactive', can_rejoin: true })).shows_can_rejoin).toBe(true)
    expect(departure_row_view(group({ reason: 'kicked_other', can_rejoin: false })).shows_can_rejoin).toBe(true)
    expect(departure_row_view(group({ reason: 'left' })).shows_can_rejoin).toBe(false)
    expect(departure_row_view(group()).shows_can_rejoin).toBe(false)
})

test('a row is answered once it has a reason', () => {
    expect(departure_row_view(group()).answered).toBe(false)
    expect(departure_row_view(group({ reason: 'left' })).answered).toBe(true)
})

test('the answer form parses ticked rows and the choice', () => {
    const form = new FormData()
    form.append('rows', '1,2')
    form.append('rows', '7')
    form.append('reason', 'kicked_other')
    form.append('can_rejoin', 'no')
    form.append('note', ' Awoxed ')
    expect(parse_departure_answer(form)).toEqual({
        departure_ids: [1, 2, 7],
        reason: 'kicked_other',
        can_rejoin: false,
        note: 'Awoxed',
    })
})

test('left drops can rejoin, and junk rows are ignored', () => {
    const form = new FormData()
    form.append('rows', 'x,3')
    form.append('reason', 'left')
    form.append('can_rejoin', 'yes')
    expect(parse_departure_answer(form)).toEqual({
        departure_ids: [3],
        reason: 'left',
        can_rejoin: null,
        note: '',
    })
})

test('an unknown reason parses to null', () => {
    const form = new FormData()
    form.append('rows', '3')
    form.append('reason', 'bored')
    expect(parse_departure_answer(form)).toBeNull()
})

test('history tags: a flag beats the reason', async () => {
    const { history_tag, has_active_flag } = await import('@helpers/corporations/departures')
    const entry = {
        departure_id: 1, corporation_id: 98000001, corporation_name: 'Example Corp',
        left_at: '2026-11-09T12:00:00Z', reason: 'kicked_other', can_rejoin: false,
        note: 'Awoxed', answered_by_name: 'Arkan Veld', flag_active: true,
    }
    expect(history_tag(entry)).toBe('cant_rejoin')
    expect(history_tag({ ...entry, flag_active: false })).toBe('other_kick')
    expect(history_tag({ ...entry, flag_active: false, reason: 'kicked_inactive' })).toBe('inactive_kick')
    expect(history_tag({ ...entry, flag_active: false, reason: 'left' })).toBe('left')
    expect(has_active_flag([entry])).toBe(true)
    expect(has_active_flag(null)).toBe(false)
})
