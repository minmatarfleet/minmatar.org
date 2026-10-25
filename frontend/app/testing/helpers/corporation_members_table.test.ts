import { describe, expect, it } from 'vitest'
import type { CorporationMemberDetails } from '@dtypes/api.minmatar.org'
import {
    build_member_roster,
    corporation_member_attention,
    corporation_member_in_view,
    corporation_members_csv,
    parse_member_params,
    corporation_member_characters,
    corporation_member_primary,
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
                timezone: { brackets: ['EUTZ'], source: 'activity' },
            }),
            member({
                character_id: 1,
                character_name: 'Director Dan',
                user_name: 'dan',
                primary_character_id: 1,
                primary_character_name: 'Director Dan',
                fleets_90d: 1,
                token_count: 1,
                timezone: { brackets: ['EUTZ'], source: 'activity' },
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
                timezone: { brackets: ['EUTZ'], source: 'activity' },
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

    it('sorts timezone by bracket order and paginates', () => {
        const grouped = group_corporation_members([
            member({
                character_id: 1,
                character_name: 'Ann',
                timezone: { brackets: ['EUTZ'], source: 'activity' },
            }),
            member({
                character_id: 2,
                character_name: 'Zed',
                timezone: { brackets: ['USTZ+'], source: 'declared' },
            }),
            member({
                character_id: 3,
                character_name: 'Mia',
                timezone: { brackets: [], source: null },
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
            member({ character_id: 1, character_name: 'Director Dan', user_name: 'dan', primary_character_id: 1, primary_character_name: 'Director Dan', timezone: { brackets: ['EUTZ'], source: 'activity' }, community_status: 'active' }),
            member({ character_id: 2, character_name: 'Alt Ace', user_name: 'dan', primary_character_id: 1, primary_character_name: 'Director Dan' }),
            member({ character_id: 3, character_name: 'Trial Tom', user_name: 'tom', primary_character_id: 3, primary_character_name: 'Trial Tom', timezone: { brackets: ['USTZ+'], source: 'declared' }, community_status: 'trial' }),
            member({ character_id: 4, character_name: 'Quiet Quinn', user_name: 'quinn', primary_character_id: 4, primary_character_name: 'Quiet Quinn' }),
        ])
        const names = (filters: Parameters<typeof filter_corporation_member_rows>[1]) =>
            filter_corporation_member_rows(rows, filters).map((row) => corporation_member_primary(row).character_name).sort()

        expect(names({ query: 'ace' })).toEqual(['Director Dan'])
        expect(names({ query: '', timezone: 'EUTZ' })).toEqual(['Director Dan'])
        // A base filter takes in the late bracket too.
        expect(names({ query: '', timezone: 'USTZ' })).toEqual(['Trial Tom'])
        expect(names({ query: '', timezone: 'none' })).toEqual(['Quiet Quinn'])
        expect(names({ query: '', status: 'trial' })).toEqual(['Trial Tom'])
        expect(names({ query: '', status: 'none' })).toEqual(['Quiet Quinn'])
        expect(names({ query: 'ace', status: 'trial' })).toEqual([])
    })

    it('keeps the person timezone from whichever character carries it', () => {
        const [row] = group_corporation_members([
            member({ character_id: 5, character_name: 'Main', user_name: 'd', primary_character_id: 5, timezone: { brackets: [], source: null } }),
            member({ character_id: 6, character_name: 'Alt', user_name: 'd', primary_character_id: 5, timezone: { brackets: ['AUTZ'], source: 'declared' } }),
        ])
        expect(row.timezone).toEqual({ brackets: ['AUTZ'], source: 'declared' })
    })

    it('parses only known timezone filters from the URL', () => {
        expect(parse_member_params(new URLSearchParams('tz=EUTZ')).timezone).toBe('EUTZ')
        expect(parse_member_params(new URLSearchParams('tz=EU')).timezone).toBeNull()
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

describe('roster views, attention and export', () => {
    const now = new Date('2026-09-21T00:00:00Z')
    const linked = (overrides: Partial<CorporationMemberDetails> & Pick<CorporationMemberDetails, 'character_id' | 'character_name'>) =>
        member({ user_name: overrides.character_name.toLowerCase(), registered: true, token_level: 'Basic', ...overrides })

    it('picks one attention flag per person, most urgent first', () => {
        const rows = group_corporation_members([
            linked({ character_id: 1, character_name: 'Suspended', esi_suspended: true, trial_ready: true }),
            member({ character_id: 2, character_name: 'Stranger' }),
            linked({ character_id: 3, character_name: 'Main', primary_character_id: 3, primary_character_name: 'Main' }),
            member({ character_id: 4, character_name: 'Loose Alt', user_name: 'main', primary_character_id: 3, primary_character_name: 'Main', registered: false }),
            linked({ character_id: 5, character_name: 'Ready', trial_ready: true, trial_reason: '4 fleets' }),
        ])
        const by_name = Object.fromEntries(rows.map((row) => [row.character_name, corporation_member_attention(row)]))
        expect(by_name).toEqual({
            Suspended: 'esi_suspended',
            Stranger: 'no_account',
            Main: 'token_missing',
            Ready: 'trial_ready',
        })
    })

    it('filters by view against people, not characters', () => {
        const rows = group_corporation_members([
            linked({ character_id: 1, character_name: 'Flyer', fleets_90d: 5, corp_joined_at: '2024-01-01T00:00:00Z' }),
            linked({ character_id: 2, character_name: 'Quiet', fleets_90d: 0, corp_joined_at: '2023-01-01T00:00:00Z' }),
            linked({ character_id: 3, character_name: 'Rookie', fleets_90d: 1, corp_joined_at: '2026-08-01T00:00:00Z' }),
            member({ character_id: 4, character_name: 'Stranger' }),
        ])
        const names = (view: Parameters<typeof corporation_member_in_view>[1]) =>
            rows.filter((row) => corporation_member_in_view(row, view, now)).map((row) => row.character_name).sort()
        expect(names('all')).toEqual(['Flyer', 'Quiet', 'Rookie'])
        expect(names('flying')).toEqual(['Flyer'])
        expect(names('quiet')).toEqual(['Quiet'])
        expect(names('new')).toEqual(['Rookie'])
        expect(names('unlinked')).toEqual(['Stranger'])
    })

    it('counts a fleet once per person and merges alt dates', () => {
        const [row] = group_corporation_members([
            linked({ character_id: 1, character_name: 'Main', primary_character_id: 1, primary_character_name: 'Main', fleets_90d: 3, person_fleets_90d: 4, weekly_fleets: [0, 1, 3], corp_joined_at: '2024-05-01T00:00:00Z', last_fleet_at: '2026-09-01T00:00:00Z' }),
            linked({ character_id: 2, character_name: 'Alt', user_name: 'main', primary_character_id: 1, primary_character_name: 'Main', fleets_90d: 3, person_fleets_90d: 4, weekly_fleets: [0, 1, 3], corp_joined_at: '2023-05-01T00:00:00Z', last_fleet_at: '2026-09-10T00:00:00Z' }),
        ])
        expect(row.fleets_90d).toBe(4)
        expect(row.weekly_fleets).toEqual([0, 1, 3])
        expect(row.corp_joined_at).toBe('2023-05-01T00:00:00Z')
        expect(row.last_fleet_at).toBe('2026-09-10T00:00:00Z')
    })

    it('parses params, sorts, keeps picked rows and writes CSV', () => {
        const params = parse_member_params(new URLSearchParams('view=bogus&sort=joined&ids=2,x,3'))
        expect(params.view).toBe('all')
        expect(params.sort).toBe('joined')
        expect(params.ids).toEqual([2, 3])
        const rows = group_corporation_members([
            linked({ character_id: 1, character_name: 'Old', corp_joined_at: '2022-01-01T00:00:00Z' }),
            linked({ character_id: 2, character_name: 'New, "Bob"', corp_joined_at: '2026-01-01T00:00:00Z' }),
            linked({ character_id: 3, character_name: 'Mid', corp_joined_at: '2024-01-01T00:00:00Z' }),
        ])
        const roster = build_member_roster(rows, params)
        expect(roster.map((row) => row.character_id)).toEqual([3, 2])
        const csv = corporation_members_csv(roster).split('\n')
        expect(csv[0]).toMatch(/^Pilot,Alts,Status/)
        expect(csv[2]).toMatch(/^"New, ""Bob""",/)
    })
})
