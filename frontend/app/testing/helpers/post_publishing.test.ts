import { describe, expect, it } from 'vitest'

import type { DiscordChannel, PublishableGroup } from '@dtypes/api.minmatar.org'
import { post_host_fields } from '@helpers/fetching/posts'
import {
    HOST_YOU,
    announce_hint_key,
    group_discord_info,
    group_forces_members_only,
    group_posts_href,
    host_group_ref_ui,
    post_host_options,
    post_publishing_params,
    selected_host,
} from '@helpers/post_publishing'

function group(id: number, overrides: Partial<PublishableGroup> = {}): PublishableGroup {
    return {
        id,
        code: `group_${id}`,
        name: `Group ${id}`,
        tribe_id: 7,
        tribe_name: 'Capitals',
        member_count: 12,
        allow_alliance_posts: true,
        allow_open_fleets: false,
        ...overrides,
    }
}

function form(fields: Record<string, string>) {
    return (name: string) => fields[name] ?? null
}

const groups = [group(1), group(2, { allow_alliance_posts: false })]

describe('host_group_ref_ui', () => {
    it('is null for an alliance post and a plain ref for a group post', () => {
        expect(host_group_ref_ui(null)).toBeNull()
        expect(host_group_ref_ui(undefined)).toBeNull()
        expect(host_group_ref_ui({ id: 1, code: 'dreads', name: 'Dreads', tribe_id: 7, tribe_name: 'Capitals' })).toEqual({
            id: 1,
            code: 'dreads',
            name: 'Dreads',
            tribe_id: 7,
            tribe_name: 'Capitals',
        })
    })
})

describe('post_host_fields', () => {
    it('adds nothing for an alliance post, so its card is exactly as before', () => {
        expect(post_host_fields({ host_group: null, members_only: false })).toEqual({})
        expect(post_host_fields({})).toEqual({})
    })

    it('carries the group and members_only for a group post', () => {
        const fields = post_host_fields({
            host_group: { id: 1, code: 'dreads', name: 'Dreads', tribe_id: 7, tribe_name: 'Capitals' },
            members_only: true,
        })

        expect(fields.host_group?.name).toBe('Dreads')
        expect(fields.members_only).toBe(true)
    })
})

describe('post_host_options', () => {
    it('puts You first, then one card per group', () => {
        const options = post_host_options(
            groups,
            { label: 'Casper', sub: 'Alliance post', image_url: '/me.png' },
            (g) => `${g.tribe_name} · ${g.member_count}`,
        )

        expect(options.map((option) => option.value)).toEqual([HOST_YOU, '1', '2'])
        expect(options[0]).toMatchObject({ label: 'Casper', image_url: '/me.png' })
        expect(options[1]).toMatchObject({ label: 'Group 1', sub: 'Capitals · 12' })
    })
})

describe('selected_host', () => {
    it('picks the ?host group only when the pilot can post as it', () => {
        expect(selected_host('2', groups)).toBe('2')
        expect(selected_host('99', groups)).toBe(HOST_YOU)
        expect(selected_host('abc', groups)).toBe(HOST_YOU)
        expect(selected_host(null, groups)).toBe(HOST_YOU)
    })
})

describe('post_publishing_params', () => {
    it('sends nothing for a post as yourself, so the request is today\'s', () => {
        expect(post_publishing_params({ get: form({ host: HOST_YOU }), groups })).toEqual({})
        expect(post_publishing_params({ get: form({}), groups })).toEqual({})
        expect(post_publishing_params({ get: form({ host: 'junk' }), groups })).toEqual({})
    })

    it('reads the picked group\'s own visibility and announce fields', () => {
        const params = post_publishing_params({
            get: form({ host: '1', visibility_1: 'members', announce_1: 'on', visibility_2: 'alliance' }),
            groups,
        })

        expect(params).toEqual({ host_group_id: 1, members_only: true, announce: true })
    })

    it('defaults to the whole alliance and no announcement', () => {
        expect(post_publishing_params({ get: form({ host: '1' }), groups })).toEqual({
            host_group_id: 1,
            members_only: false,
            announce: false,
        })
    })

    it('forces members only when the group has alliance posts off', () => {
        const params = post_publishing_params({ get: form({ host: '2', visibility_2: 'alliance' }), groups })

        expect(params.members_only).toBe(true)
        expect(group_forces_members_only(groups[1])).toBe(true)
        expect(group_forces_members_only(groups[0])).toBe(false)
        expect(group_forces_members_only(undefined)).toBe(false)
    })

    it('ignores the other groups\' hidden fields', () => {
        const params = post_publishing_params({
            get: form({ host: '1', announce_2: 'on', visibility_2: 'members' }),
            groups,
        })

        expect(params).toEqual({ host_group_id: 1, members_only: false, announce: false })
    })
})

describe('group_discord_info', () => {
    const channels: DiscordChannel[] = [{ id: '555', name: 'capitals', type: 'text' }]

    it('names the channel and role when both are known', () => {
        const info = group_discord_info({ effective_discord_channel_id: '555', discord_role_name: 'Tribe Group - Dreads' }, channels)

        expect(info).toEqual({ has_channel: true, channel_name: '#capitals', role_name: 'Tribe Group - Dreads' })
        expect(announce_hint_key(info.channel_name, info.role_name, info.has_channel)).toBe('tribes.publishing.post.announce_channel_role')
    })

    it('falls back to a generic line when the channel list is unreadable', () => {
        const info = group_discord_info({ effective_discord_channel_id: '555', discord_role_name: null }, [])

        expect(info).toEqual({ has_channel: true, channel_name: null, role_name: null })
        expect(announce_hint_key(info.channel_name, info.role_name, info.has_channel)).toBe('tribes.publishing.post.announce_group_channel')
    })

    it('says nothing will be posted when the group has no channel', () => {
        const info = group_discord_info({ effective_discord_channel_id: null, discord_role_name: 'x' }, channels)

        expect(info.has_channel).toBe(false)
        expect(announce_hint_key(info.channel_name, info.role_name, info.has_channel)).toBe('tribes.publishing.post.announce_no_channel')
    })

    it('assumes a channel for a group that could not be fetched', () => {
        expect(group_discord_info(null, channels).has_channel).toBe(true)
    })
})

describe('group_posts_href', () => {
    it('links to the group page Posts tab', () => {
        expect(group_posts_href({ tribe_id: 7, id: 3 })).toBe('/alliance/tribes/7/3/#posts')
    })
})
