import { describe, expect, it } from 'vitest'

import type { TribeGroupRosterEntry } from '@dtypes/api.minmatar.org'
import {
    group_roster_by_rank,
    roster_corporation_filters,
} from '@helpers/tribe_roster'

function entry(
    overrides: Partial<TribeGroupRosterEntry> & {
        primary_character_name: string
    },
): TribeGroupRosterEntry {
    return {
        user_id: 1,
        primary_character_id: 1,
        corporation_id: null,
        corporation_name: null,
        rank_id: null,
        rank_code: null,
        rank_name: null,
        rank_sort_order: null,
        approved_at: null,
        ...overrides,
    }
}

describe('group_roster_by_rank', () => {
    it('stays flat when nobody has a rank', () => {
        const sections = group_roster_by_rank(
            [
                entry({ primary_character_name: 'Zed', user_id: 2 }),
                entry({ primary_character_name: 'Ann', user_id: 1 }),
            ],
            'Members',
        )

        expect(sections).toHaveLength(1)
        expect(sections[0].heading).toBeNull()
        expect(sections[0].members.map((m) => m.primary_character_name)).toEqual([
            'Ann',
            'Zed',
        ])
    })

    it('stays flat when everyone shares one rank', () => {
        const sections = group_roster_by_rank(
            [
                entry({
                    primary_character_name: 'Bob',
                    rank_id: 1,
                    rank_name: 'Pilot',
                    rank_sort_order: 1,
                }),
                entry({
                    primary_character_name: 'Ann',
                    user_id: 2,
                    primary_character_id: 2,
                    rank_id: 1,
                    rank_name: 'Pilot',
                    rank_sort_order: 1,
                }),
            ],
            'Members',
        )

        expect(sections).toHaveLength(1)
        expect(sections[0].heading).toBeNull()
        expect(sections[0].show_rank_on_cards).toBe(false)
    })

    it('groups by rank sort order with unranked last', () => {
        const sections = group_roster_by_rank(
            [
                entry({
                    primary_character_name: 'Skirm A',
                    user_id: 1,
                    primary_character_id: 1,
                    rank_id: 2,
                    rank_name: 'Skirmish FC',
                    rank_sort_order: 2,
                }),
                entry({
                    primary_character_name: 'Strat B',
                    user_id: 2,
                    primary_character_id: 2,
                    rank_id: 1,
                    rank_name: 'Strategic FC',
                    rank_sort_order: 1,
                }),
                entry({
                    primary_character_name: 'No Rank',
                    user_id: 3,
                    primary_character_id: 3,
                }),
                entry({
                    primary_character_name: 'Skirm B',
                    user_id: 4,
                    primary_character_id: 4,
                    rank_id: 2,
                    rank_name: 'Skirmish FC',
                    rank_sort_order: 2,
                }),
            ],
            'Members',
        )

        expect(sections.map((s) => s.heading)).toEqual([
            'Strategic FC',
            'Skirmish FC',
            'Members',
        ])
        expect(sections[0].members.map((m) => m.primary_character_name)).toEqual([
            'Strat B',
        ])
        expect(sections[1].members.map((m) => m.primary_character_name)).toEqual([
            'Skirm A',
            'Skirm B',
        ])
        expect(sections[2].members.map((m) => m.primary_character_name)).toEqual([
            'No Rank',
        ])
        expect(sections.every((s) => s.show_rank_on_cards === false)).toBe(true)
    })
})

describe('roster_corporation_filters', () => {
    it('returns empty when there is only one corporation', () => {
        expect(
            roster_corporation_filters(
                [
                    entry({
                        primary_character_name: 'A',
                        corporation_id: 1,
                        corporation_name: 'Rattini Tribe',
                    }),
                    entry({
                        primary_character_name: 'B',
                        user_id: 2,
                        primary_character_id: 2,
                        corporation_id: 1,
                        corporation_name: 'Rattini Tribe',
                    }),
                ],
                'All',
                'Unknown corporation',
            ),
        ).toEqual([])
    })

    it('builds all + corp chips with counts', () => {
        const filters = roster_corporation_filters(
            [
                entry({
                    primary_character_name: 'A',
                    corporation_id: 2,
                    corporation_name: 'Soltech Armada',
                }),
                entry({
                    primary_character_name: 'B',
                    user_id: 2,
                    primary_character_id: 2,
                    corporation_id: 1,
                    corporation_name: 'Rattini Tribe',
                }),
                entry({
                    primary_character_name: 'C',
                    user_id: 3,
                    primary_character_id: 3,
                    corporation_id: 1,
                    corporation_name: 'Rattini Tribe',
                }),
                entry({
                    primary_character_name: 'D',
                    user_id: 4,
                    primary_character_id: 4,
                }),
            ],
            'All',
            'Unknown corporation',
        )

        expect(filters[0]).toEqual({
            id: 'all',
            corporation_id: null,
            label: 'All',
            count: 4,
        })
        expect(filters.slice(1).map((f) => [f.id, f.label, f.count])).toEqual([
            ['1', 'Rattini Tribe', 2],
            ['2', 'Soltech Armada', 1],
            ['none', 'Unknown corporation', 1],
        ])
    })
})
