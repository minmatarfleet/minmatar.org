import { describe, expect, it } from 'vitest'

import type { TribeGroup, TribeMembership } from '@dtypes/api.minmatar.org'
import { tribe_group_apply_ui_state } from '@helpers/tribe_group_apply_ui'

function group(overrides: Partial<TribeGroup> = {}): TribeGroup {
    return {
        id: 1,
        tribe_id: 1,
        tribe_name: 'Pulse',
        name: 'Fleet Commanders',
        code: 'pulse.fleet-commanders',
        description: '',
        member_count: 0,
        requirements: [],
        ...overrides,
    }
}

function membership(status: TribeMembership['status']): TribeMembership {
    return {
        id: 10,
        user_id: 5,
        tribe_group_id: 1,
        status,
        characters: [],
    }
}

describe('tribe_group_apply_ui_state', () => {
    it('shows apply for guests when not blocked by trial', () => {
        const state = tribe_group_apply_ui_state({
            group: group({ can_apply: true }),
            membership: null,
            is_auth: false,
            is_leader: false,
            user_on_trial: false,
        })

        expect(state.can_show_apply).toBe(true)
        expect(state.show_ineligible).toBe(false)
    })

    it('blocks apply for ineligible authenticated users with affiliation names', () => {
        const state = tribe_group_apply_ui_state({
            group: group({
                can_apply: false,
                allowed_affiliations: [{ id: 1, name: 'Alliance' }],
            }),
            membership: null,
            is_auth: true,
            is_leader: false,
            user_on_trial: false,
        })

        expect(state.can_show_apply).toBe(false)
        expect(state.show_ineligible).toBe(true)
        expect(state.affiliation_names).toBe('Alliance')
    })

    it('hides apply when trial is required and user is on trial', () => {
        const state = tribe_group_apply_ui_state({
            group: group({ can_apply: true, require_off_trial: true }),
            membership: null,
            is_auth: true,
            is_leader: false,
            user_on_trial: true,
        })

        expect(state.can_show_apply).toBe(false)
        expect(state.blocked_by_trial).toBe(true)
    })
})
