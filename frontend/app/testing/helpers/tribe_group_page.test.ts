import { describe, expect, it } from 'vitest'
import type { TribeEvent } from '@dtypes/api.minmatar.org'
import {
    TRIBE_GROUP_HASH_ALIASES,
    event_row,
    fleet_visibility,
    group_by_eve_day,
    post_tile,
    sort_newest_first,
    split_events,
    tribe_group_tab_ids,
    tribe_new_menu_items,
    type GroupPostSource,
    type TribeGroupTabInput,
} from '@helpers/tribe_group_page'

const nothing: TribeGroupTabInput = {
    has_about: false,
    has_guides: false,
    has_activity: false,
    fleet_count: 0,
    event_count: 0,
    post_count: 0,
    can_schedule_fleets: false,
    can_create_events: false,
    can_post: false,
    can_manage: false,
}

describe('tribe group tabs', () => {
    it('always shows Requirements and Members, and nothing else when empty', () => {
        expect(tribe_group_tab_ids(nothing)).toEqual(['requirements', 'members'])
    })

    it('keeps the contract order with everything shown', () => {
        expect(tribe_group_tab_ids({
            has_about: true,
            has_guides: true,
            has_activity: true,
            fleet_count: 1,
            event_count: 1,
            post_count: 1,
            can_schedule_fleets: false,
            can_create_events: false,
            can_post: false,
            can_manage: true,
        })).toEqual(['about', 'requirements', 'guides', 'activity', 'members', 'fleets', 'events', 'posts', 'settings'])
    })

    it('shows an empty tab to a viewer who can add to it', () => {
        expect(tribe_group_tab_ids({ ...nothing, can_schedule_fleets: true })).toContain('fleets')
        expect(tribe_group_tab_ids({ ...nothing, can_create_events: true })).toContain('events')
        expect(tribe_group_tab_ids({ ...nothing, can_post: true })).toContain('posts')
    })

    it('shows content tabs to outsiders and never Settings', () => {
        const tabs = tribe_group_tab_ids({ ...nothing, fleet_count: 2, post_count: 3 })
        expect(tabs).toEqual(['requirements', 'members', 'fleets', 'posts'])
        expect(tabs).not.toContain('settings')
    })

    it('opens Posts from the old #propaganda hash', () => {
        expect(TRIBE_GROUP_HASH_ALIASES).toEqual({ propaganda: 'posts' })
    })
})

describe('tribe group New menu', () => {
    const none = { can_post: false, can_schedule_fleets: false, can_create_events: false }

    it('is empty without a publishing flag', () => {
        expect(tribe_new_menu_items(none, 2, 7)).toEqual([])
    })

    it('links each form with the group picked', () => {
        expect(tribe_new_menu_items({ can_post: true, can_schedule_fleets: true, can_create_events: true }, 2, 7)).toEqual([
            { kind: 'post', href: '/alliance/propaganda/new/editor?host=7' },
            { kind: 'fleet', href: '/fleets/add/?host=7' },
            { kind: 'event', href: '/alliance/tribes/2/7/events/new' },
        ])
    })

    it('offers only what the viewer may publish', () => {
        expect(tribe_new_menu_items({ ...none, can_create_events: true }, 2, 7).map((item) => item.kind)).toEqual(['event'])
    })
})

describe('tribe group fleets', () => {
    it('marks a fleet open only when it was opened to the alliance', () => {
        expect(fleet_visibility({ open_to_alliance: true })).toBe('open')
        expect(fleet_visibility({ open_to_alliance: false })).toBe('members_only')
    })

    it('groups by EVE day in start order', () => {
        const days = group_by_eve_day([
            { id: 3, start_time: '2026-10-24T18:00:00Z' },
            { id: 1, start_time: '2026-10-22T19:00:00Z' },
            { id: 2, start_time: '2026-10-22T23:30:00Z' },
        ])
        expect(days.map((day) => [day.key, day.fleets.map((fleet) => fleet.id)])).toEqual([
            ['2026-10-22', [1, 2]],
            ['2026-10-24', [3]],
        ])
    })
})

describe('tribe group posts', () => {
    const post = (overrides: Partial<GroupPostSource> = {}): GroupPostSource => ({
        post_id: 5,
        title: 'Siege drills',
        seo_description: 'Bring a Revelation.',
        author_character_id: 90,
        author_character_name: 'Casper Sullivan',
        date_posted: '2026-10-01T10:00:00Z',
        members_only: false,
        host_group: { id: 7, code: 'capitals.dreads', name: 'Dreads', tribe_id: 2, tribe_name: 'Capitals' },
        image: 'https://example.test/a.png',
        ...overrides,
    })

    it('builds a tile for the group\'s own post', () => {
        expect(post_tile(post(), 7, '/alliance/propaganda/5')).toEqual({
            id: 5,
            title: 'Siege drills',
            excerpt: 'Bring a Revelation.',
            image_url: 'https://example.test/a.png',
            href: '/alliance/propaganda/5',
            author_character_id: 90,
            author_character_name: 'Casper Sullivan',
            date: '2026-10-01T10:00:00Z',
            members_only: false,
            tagged: false,
        })
    })

    it('calls a post tagged when another pilot or group published it', () => {
        expect(post_tile(post({ host_group: null }), 7, '').tagged).toBe(true)
        expect(post_tile(post({ host_group: { id: 8, code: '', name: 'Carriers', tribe_id: 2, tribe_name: 'Capitals' } }), 7, '').tagged).toBe(true)
    })

    it('falls back to the crest when the post has no image', () => {
        expect(post_tile(post({ image: '' }), 7, '').image_url).toBeNull()
        expect(post_tile(post({ members_only: true }), 7, '').members_only).toBe(true)
    })

    it('sorts newest first', () => {
        const sorted = sort_newest_first([
            { date_posted: '2026-01-01T00:00:00Z', id: 'old' },
            { date_posted: '2026-03-01T00:00:00Z', id: 'new' },
        ])
        expect(sorted.map((item) => item.id)).toEqual(['new', 'old'])
    })
})

describe('tribe group events', () => {
    const event = (overrides: Partial<TribeEvent> = {}): TribeEvent => ({
        id: 1,
        title: 'Town Hall #38',
        description: '',
        starts_at: '2026-11-14T19:00:00Z',
        ends_at: '2026-11-14T20:30:00Z',
        recurrence: 'monthly',
        recurrence_label: 'Every 2nd Saturday of the month',
        where_kind: 'voice',
        where_label: 'Town Hall',
        voice_channel_id: '111',
        voice_channel_name: 'Town Hall',
        location: '',
        members_only: false,
        announce: true,
        discord_event_id: '999',
        discord_event_url: 'https://discord.com/events/1/999',
        interested_count: 42,
        status: 'scheduled',
        cancelled_at: null,
        created_at: '2026-10-01T00:00:00Z',
        updated_at: '2026-10-01T00:00:00Z',
        created_by: null,
        can_manage: true,
        tribe_group: { id: 13, code: 'pulse.thinkspeak', name: 'Thinkspeak', tribe_id: 4, tribe_name: 'Pulse' },
        ...overrides,
    })

    it('puts the first scheduled event in the hero and the rest in start order', () => {
        const cancelled = event({ id: 2, status: 'cancelled', starts_at: '2026-11-01T19:00:00Z' })
        const later = event({ id: 3, starts_at: '2026-12-12T19:00:00Z' })
        const next = event({ id: 1 })
        const { next: hero, rest } = split_events([later, next, cancelled])
        expect(hero?.id).toBe(1)
        expect(rest.map((item) => item.id)).toEqual([2, 3])
    })

    it('has no hero when nothing is scheduled', () => {
        expect(split_events([event({ status: 'cancelled' })]).next).toBeNull()
    })

    it('reads stage channels from the channel list', () => {
        const row = event_row(event(), {
            cover_url: '/c.webp',
            edit_href: '/edit',
            voice_channels: [{ id: '111', name: 'Town Hall', type: 'stage' }],
        })
        expect(row.where_kind).toBe('stage')
        expect(row.recurrence_label).toBe('Every 2nd Saturday of the month')
        expect(row.edit_href).toBe('/edit')
        expect(event_row(event(), { cover_url: null, edit_href: null }).where_kind).toBe('voice')
    })

    it('drops the label of a one-off event and the edit link of a cancelled one', () => {
        const row = event_row(event({ recurrence: 'none', recurrence_label: 'Does not repeat', status: 'cancelled' }), {
            cover_url: null,
            edit_href: '/edit',
        })
        expect(row.recurrence_label).toBeNull()
        expect(row.edit_href).toBeNull()
        expect(event_row(event({ where_kind: 'place' }), { cover_url: null, edit_href: null }).where_kind).toBe('place')
    })
})
