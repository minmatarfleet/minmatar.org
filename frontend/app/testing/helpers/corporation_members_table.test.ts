import { describe, expect, it } from 'vitest'
import type { CorporationMemberDetails } from '@dtypes/api.minmatar.org'
import {
    corporation_member_characters,
    corporation_member_primary,
    corporation_member_timezones,
    filter_corporation_member_rows,
    group_corporation_members,
    paginate_corporation_member_rows,
    sort_corporation_member_rows,
} from '@helpers/corporations/detail'

function member(overrides: Partial<CorporationMemberDetails> & Pick<CorporationMemberDetails, 'character_id' | 'character_name'>): CorporationMemberDetails {
    return {
        registered: false,
        exempt: false,
        esi_suspended: false,
        token_count: 0,
        token_level: '',
        fleets_90d: 0,
        kills_90d: 0,
        voice_hours_90d: 0,
        observed_prime_times: [],
        ...overrides,
    }
}

describe('corporation member table', () => {
    it('groups alts under the primary character', () => {
        const rows = group_corporation_members([
            member({
                character_id: 2,
                character_name: 'Alt Ace',
                user_name: 'dan',
                primary_character_id: 1,
                primary_character_name: 'Director Dan',
                fleets_90d: 4,
                registered: true,
                observed_prime_times: ['EU'],
            }),
            member({
                character_id: 1,
                character_name: 'Director Dan',
                user_name: 'dan',
                primary_character_id: 1,
                primary_character_name: 'Director Dan',
                fleets_90d: 1,
                token_count: 1,
                observed_prime_times: ['EU'],
            }),
            member({
                character_id: 9,
                character_name: 'Solo Pilot',
                fleets_90d: 2,
            }),
        ])

        expect(rows).toHaveLength(2)
        const grouped = rows.find((row) => row.character_name === 'Director Dan')
        expect(grouped?.alts.map((alt) => alt.character_name)).toEqual(['Alt Ace'])
        expect(grouped?.fleets_90d).toBe(5)
        expect(grouped?.token_count).toBe(1)
        expect(grouped?.registered).toBe(true)
        expect(grouped?.primary).toBeNull()
        expect(corporation_member_primary(grouped!).character_name).toBe('Director Dan')
        expect(corporation_member_characters(grouped!).map((alt) => alt.character_name)).toEqual(['Alt Ace'])
        expect(rows.some((row) => row.character_name === 'Solo Pilot')).toBe(true)
    })

    it('shows the main when only an alt is in the corporation', () => {
        const [row] = group_corporation_members([
            member({
                character_id: 2,
                character_name: 'Alt Ace',
                primary_character_id: 1,
                primary_character_name: 'Director Dan',
                observed_prime_times: ['EU'],
            }),
            member({
                character_id: 3,
                character_name: 'Alt Bee',
                primary_character_id: 1,
                primary_character_name: 'Director Dan',
            }),
        ])

        expect(corporation_member_primary(row).character_name).toBe('Director Dan')
        expect(corporation_member_characters(row).map((alt) => alt.character_name)).toEqual(['Alt Ace', 'Alt Bee'])
        expect(filter_corporation_member_rows([row], {
            registered_only: false,
            query: 'bee',
        })).toHaveLength(1)
        expect(filter_corporation_member_rows([row], {
            registered_only: false,
            query: 'director',
        })).toHaveLength(1)
    })

    it('sorts timezone by observed buckets and paginates', () => {
        const grouped = group_corporation_members([
            member({
                character_id: 1,
                character_name: 'Ann',
                observed_prime_times: ['EU'],
                prime_time: 'US',
            }),
            member({
                character_id: 2,
                character_name: 'Zed',
                observed_prime_times: ['US'],
                prime_time: 'EU',
            }),
            member({
                character_id: 3,
                character_name: 'Mia',
                prime_time: 'US',
            }),
        ])
        const sorted = sort_corporation_member_rows(grouped, 'timezone')
        expect(sorted.map((row) => row.character_name)).toEqual(['Zed', 'Ann', 'Mia'])

        const page = paginate_corporation_member_rows(sorted, 2, 2)
        expect(page.page).toBe(2)
        expect(page.total_pages).toBe(2)
        expect(page.rows.map((row) => row.character_name)).toEqual(['Mia'])
    })

    it('filters by name, alt, and registration', () => {
        const grouped = group_corporation_members([
            member({
                character_id: 1,
                character_name: 'Director Dan',
                user_name: 'dan',
                primary_character_id: 1,
                primary_character_name: 'Director Dan',
                registered: false,
            }),
            member({
                character_id: 2,
                character_name: 'Alt Ace',
                user_name: 'dan',
                primary_character_id: 1,
                primary_character_name: 'Director Dan',
                registered: true,
            }),
        ])
        expect(filter_corporation_member_rows(grouped, {
            registered_only: true,
            query: '',
        })).toHaveLength(1)
        expect(filter_corporation_member_rows(grouped, {
            registered_only: false,
            query: 'ace',
        }).map((row) => row.character_name)).toEqual(['Director Dan'])
    })

    it('filters by timezone and community status, searching alts too', () => {
        const rows = group_corporation_members([
            member({ character_id: 1, character_name: 'Director Dan', user_name: 'dan', primary_character_id: 1, primary_character_name: 'Director Dan', observed_prime_times: ['EU'], community_status: 'active' }),
            member({ character_id: 2, character_name: 'Alt Ace', user_name: 'dan', primary_character_id: 1, primary_character_name: 'Director Dan' }),
            member({ character_id: 3, character_name: 'Trial Tom', user_name: 'tom', primary_character_id: 3, primary_character_name: 'Trial Tom', prime_time: 'US', community_status: 'trial' }),
            member({ character_id: 4, character_name: 'Quiet Quinn', user_name: 'quinn', primary_character_id: 4, primary_character_name: 'Quiet Quinn' }),
        ])
        const names = (filters: Parameters<typeof filter_corporation_member_rows>[1]) =>
            filter_corporation_member_rows(rows, filters).map((row) => corporation_member_primary(row).character_name).sort()

        expect(names({ query: 'ace' })).toEqual(['Director Dan'])
        expect(names({ query: '', timezone: 'EU' })).toEqual(['Director Dan'])
        expect(names({ query: '', timezone: 'US' })).toEqual(['Trial Tom'])
        expect(names({ query: '', status: 'trial' })).toEqual(['Trial Tom'])
        expect(names({ query: '', status: 'none' })).toEqual(['Quiet Quinn'])
        expect(names({ query: 'ace', status: 'trial' })).toEqual([])
    })

    it('falls back to the declared timezone when no fleets were seen', () => {
        const [row] = group_corporation_members([
            member({ character_id: 5, character_name: 'Decl', user_name: 'd', prime_time: 'AP' }),
        ])
        expect(corporation_member_timezones(row)).toEqual({ codes: ['AP'], declared: true })
    })
})

describe('rows with hidden characters', () => {
    it('stay linked and keep only a count of characters', () => {
        const rows = group_corporation_members([
            member({ character_id: 1, character_name: 'Visible Main', primary_character_id: 1, primary_character_name: 'Visible Main', characters_hidden: true, hidden_character_count: 2 }),
            member({ character_id: 9, character_name: 'Unlinked Pilot' }),
        ])
        const linked = filter_corporation_member_rows(rows, { query: '', account: 'linked' })
        expect(linked.map((row) => row.character_name)).toEqual(['Visible Main'])
        expect(linked[0].hidden_character_count).toBe(2)
        expect(corporation_member_characters(linked[0])).toEqual([])
        expect(filter_corporation_member_rows(rows, { query: '', account: 'unlinked' }).map((row) => row.character_name)).toEqual(['Unlinked Pilot'])
    })
})
