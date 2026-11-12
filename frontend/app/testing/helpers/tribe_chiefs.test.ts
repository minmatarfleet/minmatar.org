import { describe, expect, test } from 'vitest'

import type { Tribe, TribeGroup } from '@dtypes/api.minmatar.org'
import { help_wanted_props } from '@helpers/tribe_chiefs'

const faye = { character_id: 2120834555, character_name: 'Faye Vaelent' }
const bear = { character_id: 634915984, character_name: 'BearThatCares' }

const tribe = (overrides: Partial<Tribe> = {}): Tribe => ({
    id: 2,
    name: 'Pulse',
    slug: 'pulse',
    description: '',
    content: '',
    image_url: null,
    banner_url: null,
    discord_channel_id: null,
    chief: faye,
    acting_chief: faye,
    chief_is_interim: false,
    can_appoint_chief: false,
    can_set_chief: false,
    can_manage_discord: false,
    has_volunteered: false,
    is_active: true,
    group_count: 7,
    total_member_count: 40,
    ...overrides,
})

const group = (overrides: Partial<TribeGroup> = {}) => ({
    id: 11,
    tribe_id: 2,
    name: 'Fishermen',
    chief: null,
    acting_chief: faye,
    chief_is_interim: true,
    can_appoint_chief: false,
    has_volunteered: false,
    ...overrides,
}) as TribeGroup

describe('help_wanted_props', () => {
    test('a chiefless group is covered by its tribe chief', () => {
        const props = help_wanted_props(tribe(), group())
        expect(props).toMatchObject({
            tribe_id: 2,
            group_id: 11,
            seat_name: 'Fishermen',
            tribe_name: 'Pulse',
            interim_name: 'Faye Vaelent',
            interim_is_executor: false,
        })
    })

    test('a group in a chiefless tribe is covered by the executor', () => {
        const props = help_wanted_props(
            tribe({ chief: null, acting_chief: bear, chief_is_interim: true }),
            group({ acting_chief: bear, can_appoint_chief: true }),
        )
        expect(props.interim_name).toBe('BearThatCares')
        expect(props.interim_is_executor).toBe(true)
        expect(props.can_appoint).toBe(true)
    })

    test('the tribe seat itself', () => {
        const props = help_wanted_props(
            tribe({ chief: null, acting_chief: bear, chief_is_interim: true, has_volunteered: true }),
        )
        expect(props.group_id).toBeNull()
        expect(props.seat_name).toBe('Pulse')
        expect(props.has_volunteered).toBe(true)
    })
})
