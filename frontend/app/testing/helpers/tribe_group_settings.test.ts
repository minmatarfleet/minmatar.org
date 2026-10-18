import { describe, expect, it } from 'vitest'
import type { TribeGroupPublishing } from '@dtypes/api.minmatar.org'
import {
    discord_settings_patch,
    parse_settings_section,
    policy_of,
    publishers_of,
    publishing_settings_patch,
} from '@helpers/tribe_group_settings'

const form = (fields: [string, string][]) => {
    const data = new FormData()
    fields.forEach(([name, value]) => data.append(name, value))
    return data
}

describe('tribe group settings sections', () => {
    it('only knows the Discord and Publishing sections', () => {
        expect(parse_settings_section('discord')).toBe('discord')
        expect(parse_settings_section('publishing')).toBe('publishing')
        expect(parse_settings_section('about')).toBeNull()
        expect(parse_settings_section(null)).toBeNull()
    })
})

describe('Discord settings patch', () => {
    it('sends the channel id as a string', () => {
        expect(discord_settings_patch(form([['discord_channel_id', '1172908092573360149']]))).toEqual({
            discord_channel_id: '1172908092573360149',
        })
    })

    it('clears back to the tribe channel when empty', () => {
        expect(discord_settings_patch(form([['discord_channel_id', '']]))).toEqual({ discord_channel_id: null })
        expect(discord_settings_patch(form([]))).toEqual({ discord_channel_id: null })
    })
})

describe('Publishing settings patch', () => {
    it('sends policies, chosen pilots and both switches', () => {
        expect(publishing_settings_patch(form([
            ['post_policy', 'chosen'],
            ['post_publishers', '9001'],
            ['post_publishers', '9002'],
            ['post_publishers', '9001'],
            ['fleet_policy', 'members'],
            ['fleet_publishers', '9003'],
            ['event_policy', 'chiefs'],
            ['allow_alliance_posts', 'on'],
        ]))).toEqual({
            allow_alliance_posts: true,
            allow_open_fleets: false,
            post_policy: 'chosen',
            post_publisher_character_ids: [9001, 9002],
            fleet_policy: 'members',
            event_policy: 'chiefs',
        })
    })

    it('sends an empty list when every chosen pilot was removed', () => {
        expect(publishing_settings_patch(form([['event_policy', 'chosen']])).event_publisher_character_ids).toEqual([])
    })

    it('treats an unknown policy as chiefs only', () => {
        expect(publishing_settings_patch(form([['post_policy', 'everyone']])).post_policy).toBe('chiefs')
    })
})

describe('Publishing settings readers', () => {
    const settings = {
        group_id: 1,
        post_policy: 'chosen',
        fleet_policy: 'chiefs',
        event_policy: 'members',
        post_publishers: [{ character_id: 1, character_name: 'Guth' }],
        fleet_publishers: [],
        event_publishers: [],
    } as unknown as TribeGroupPublishing

    it('reads a kind\'s policy and publishers', () => {
        expect(policy_of(settings, 'post')).toBe('chosen')
        expect(policy_of(settings, 'event')).toBe('members')
        expect(publishers_of(settings, 'post')).toEqual([{ character_id: 1, character_name: 'Guth' }])
    })
})
