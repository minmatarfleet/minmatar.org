import { describe, expect, it } from 'vitest'

import type { TribeGroup, TribeMembership } from '@dtypes/api.minmatar.org'
import { tribe_group_can_manage, tribe_group_is_leader } from '@helpers/tribe_group_viewer'

function group(overrides: Partial<TribeGroup> = {}): TribeGroup {
    return {
        id: 1,
        tribe_id: 1,
        tribe_name: 'Supply',
        name: 'Mining',
        code: 'supply.mining',
        description: '',
        member_count: 0,
        requirements: [],
        discord_channel_id: null,
        chief: { character_id: 91439324, character_name: 'Keldor Eternia' },
        ship_type_ids: [],
        blueprint_type_ids: [],
        is_active: true,
        ...overrides,
    }
}

function membership(overrides: Partial<TribeMembership> = {}): TribeMembership {
    return {
        id: 10,
        user_id: 5,
        tribe_group_id: 1,
        tribe_group_name: 'Mining',
        tribe_id: 1,
        status: 'active',
        rank_id: null,
        rank_code: null,
        rank_name: null,
        inactive_reason: null,
        requirement_snapshot: null,
        created_at: '',
        approved_by_id: null,
        approved_at: null,
        left_at: null,
        characters: [],
        primary_character_id: null,
        primary_character_name: '',
        ...overrides,
    }
}

describe('tribe_group_is_leader', () => {
    it('treats the group chief character on the account as leader even without membership', () => {
        expect(tribe_group_is_leader({
            group: group(),
            membership: null,
            user_characters: [{ character_id: 91439324 }],
        })).toBe(true)
    })

    it('is false when the viewer does not own the chief character', () => {
        expect(tribe_group_is_leader({
            group: group(),
            membership: membership({ primary_character_id: 1 }),
            user_characters: [{ character_id: 2 }],
        })).toBe(false)
    })
})

describe('tribe_group_can_manage', () => {
    it('follows the API can_manage flag for tribe chiefs who are not the group chief toon', () => {
        expect(tribe_group_can_manage({
            group: group({ can_manage: true, chief: { character_id: 1, character_name: 'Other' } }),
            is_leader: false,
            is_superuser: false,
        })).toBe(true)
    })

    it('is false for regular members', () => {
        expect(tribe_group_can_manage({
            group: group({ can_manage: false }),
            is_leader: false,
            is_superuser: false,
        })).toBe(false)
    })
})
