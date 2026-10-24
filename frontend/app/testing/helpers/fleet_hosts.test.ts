import { describe, expect, it } from 'vitest'
import {
    count_fleets_by_host,
    filter_fleets_by_host,
    fleet_host_fields,
    fleet_host_groups,
    fleet_types_for_host,
    fleet_visibility,
    host_group_ref,
    parse_host_filter,
    parse_host_param,
    ping_preview_request,
    tribe_group_path,
} from '@helpers/fleet_hosts'

const DREADS = { id: 1, code: 'dreads', name: 'Dreads', tribe_id: 3, tribe_name: 'Capitals' }
const MINING = { id: 6, code: 'mining', name: 'Mining', tribe_id: 4, tribe_name: 'Supply' }

const ALLIANCE_FLEET = { id: 10, host_group: null, open_to_alliance: false }
const DREADS_FLEET = { id: 11, host_group: DREADS, open_to_alliance: false }
const MINING_OPEN_FLEET = { id: 12, host_group: MINING, open_to_alliance: true }
const FLEETS = [ ALLIANCE_FLEET, DREADS_FLEET, MINING_OPEN_FLEET ]

const form = (values: Record<string, string>) => ({ get: (name: string) => values[name] ?? null })

describe('fleet_visibility', () => {
    it('tags group fleets only: members only unless open', () => {
        expect(fleet_visibility(ALLIANCE_FLEET)).toBeNull()
        expect(fleet_visibility({})).toBeNull()
        expect(fleet_visibility(DREADS_FLEET)).toBe('members_only')
        expect(fleet_visibility(MINING_OPEN_FLEET)).toBe('open')
    })
})

describe('host_group_ref', () => {
    it('keeps only the reference fields and maps a missing host to null', () => {
        expect(host_group_ref({ ...DREADS, extra: 1 } as any)).toEqual(DREADS)
        expect(host_group_ref(null)).toBeNull()
        expect(host_group_ref(undefined)).toBeNull()
    })
})

describe('tribe_group_path', () => {
    it('links the group page, optionally to a tab', () => {
        expect(tribe_group_path(DREADS)).toBe('/alliance/tribes/3/1/')
        expect(tribe_group_path(DREADS, 'fleets')).toBe('/alliance/tribes/3/1/#fleets')
    })
})

describe('hub host filter', () => {
    it('parses the query param, defaulting to all', () => {
        expect(parse_host_filter('tribe')).toBe('tribe')
        expect(parse_host_filter('mine')).toBe('mine')
        expect(parse_host_filter('alliance')).toBe('alliance')
        expect(parse_host_filter('nope')).toBe('all')
        expect(parse_host_filter(null)).toBe('all')
    })

    it('splits alliance, tribe and my-group fleets', () => {
        expect(filter_fleets_by_host(FLEETS, 'all').map(f => f.id)).toEqual([10, 11, 12])
        expect(filter_fleets_by_host(FLEETS, 'alliance').map(f => f.id)).toEqual([10])
        expect(filter_fleets_by_host(FLEETS, 'tribe').map(f => f.id)).toEqual([11, 12])
        expect(filter_fleets_by_host(FLEETS, 'mine', [6]).map(f => f.id)).toEqual([12])
        expect(filter_fleets_by_host(FLEETS, 'mine').map(f => f.id)).toEqual([])
    })

    it('counts before filtering, and lists each host group once', () => {
        expect(count_fleets_by_host(FLEETS)).toEqual({ all: 3, alliance: 1, tribe: 2 })
        expect(count_fleets_by_host([ALLIANCE_FLEET])).toEqual({ all: 1, alliance: 1, tribe: 0 })
        expect(fleet_host_groups([...FLEETS, { id: 13, host_group: DREADS }]).map(g => g.id)).toEqual([1, 6])
    })
})

describe('fleet form host fields', () => {
    const groups = [
        { id: 1, allow_open_fleets: false },
        { id: 6, allow_open_fleets: true },
    ]

    it('drops Strategic for group fleets', () => {
        expect(fleet_types_for_host(false)).toEqual(['strategic', 'non_strategic', 'training', 'npsi'])
        expect(fleet_types_for_host(true)).toEqual(['non_strategic', 'training', 'npsi'])
    })

    it('only pre-picks a ?host group the FC can schedule for', () => {
        expect(parse_host_param('6', groups)).toBe(6)
        expect(parse_host_param('7', groups)).toBeNull()
        expect(parse_host_param('x', groups)).toBeNull()
        expect(parse_host_param(null, groups)).toBeNull()
    })

    it('leaves the request as before when the form had no Host row', () => {
        expect(fleet_host_fields(form({ audience_id: '2' }), groups)).toBeNull()
    })

    it('sends no group for the Alliance host', () => {
        expect(fleet_host_fields(form({ host: 'alliance', open_to_alliance: 'on', on_schedule: 'on' }), groups))
            .toEqual({ host_group_id: null, open_to_alliance: false, on_schedule: false })
    })

    it('opens a fleet only for a group that allows it, and schedules only open fleets', () => {
        expect(fleet_host_fields(form({ host: '1', open_to_alliance: 'on', on_schedule: 'on' }), groups))
            .toEqual({ host_group_id: 1, open_to_alliance: false, on_schedule: false })
        expect(fleet_host_fields(form({ host: '6', open_to_alliance: 'on', on_schedule: 'on' }), groups))
            .toEqual({ host_group_id: 6, open_to_alliance: true, on_schedule: true })
        expect(fleet_host_fields(form({ host: '6', open_to_alliance: 'on' }), groups))
            .toEqual({ host_group_id: 6, open_to_alliance: true, on_schedule: false })
        expect(fleet_host_fields(form({ host: '6', on_schedule: 'on' }), groups))
            .toEqual({ host_group_id: 6, open_to_alliance: false, on_schedule: false })
    })

    it('keeps the switches for a group the editor no longer publishes for (the API decides)', () => {
        expect(fleet_host_fields(form({ host: '9', open_to_alliance: 'on', on_schedule: 'on' }), groups))
            .toEqual({ host_group_id: 9, open_to_alliance: true, on_schedule: true })
    })
})

describe('ping_preview_request', () => {
    it('builds an alliance preview from the audience', () => {
        expect(ping_preview_request(form({
            host: 'alliance', fleet_type: 'strategic', description: 'Form up', objective: 'Timer',
            location_id: '60003760', audience_id: '2',
        }))).toEqual({
            type: 'strategic', description: 'Form up', objective: 'Timer',
            location_id: 60003760, audience_id: 2, host_group_id: null,
        })
    })

    it('builds a group preview without an audience and never as Strategic', () => {
        expect(ping_preview_request(form({ host: '1', fleet_type: 'strategic', audience_id: '2' }))).toEqual({
            type: 'non_strategic', description: '', objective: null,
            location_id: null, audience_id: null, host_group_id: 1,
        })
    })

    it('treats a form without a Host row as an alliance fleet', () => {
        expect(ping_preview_request(form({ fleet_type: 'training', audience_id: '3' }))).toMatchObject({
            type: 'training', audience_id: 3, host_group_id: null,
        })
    })
})
