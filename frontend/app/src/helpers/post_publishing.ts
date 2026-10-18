/**
 * Pure helpers for "Publish as" on the post editor (docs/tribes/tribe-publishing.md):
 * which host options exist, which one is picked, and what the form sends.
 */
import type { DiscordChannel, HostGroupRef, PostParams, PublishableGroup, TribeGroup } from '@dtypes/api.minmatar.org'
import type { HostOptionUI, TribeGroupRefUI } from '@dtypes/layout_components'
import { tribe_group_cover } from '@helpers/tribe_covers'

/** Radio value of the "You" option: a plain alliance post, as today. */
export const HOST_YOU = 'you'

export type PostVisibility = 'alliance' | 'members'

export type PostPublishingParams = Pick<PostParams, 'host_group_id' | 'members_only' | 'announce'>

type FormValue = FormDataEntryValue | null | undefined

/** The API's group reference as a UI one, or null for an alliance post. */
export function host_group_ref_ui(host_group?: HostGroupRef | null): TribeGroupRefUI | null {
    if (!host_group) return null

    return {
        id: host_group.id,
        code: host_group.code,
        name: host_group.name,
        tribe_id: host_group.tribe_id,
        tribe_name: host_group.tribe_name,
    }
}

/** "You" first (the default), then one card per group the pilot can post as. */
export function post_host_options(
    groups: PublishableGroup[],
    you: { label: string, sub: string, image_url: string },
    group_sub: (group: PublishableGroup) => string,
): HostOptionUI[] {
    return [
        { value: HOST_YOU, label: you.label, sub: you.sub, image_url: you.image_url },
        ...groups.map((group) => ({
            value: String(group.id),
            label: group.name,
            sub: group_sub(group),
            image_url: tribe_group_cover(group.id),
        })),
    ]
}

/** `?host=<group_id>` pre-picks a group, but only one the pilot can post as. */
export function selected_host(host_param: string | null | undefined, groups: PublishableGroup[]): string {
    const group_id = parseInt(host_param ?? '')

    return groups.some((group) => group.id === group_id) ? String(group_id) : HOST_YOU
}

/** A group with alliance posts off can only publish members-only posts. */
export function group_forces_members_only(group?: Pick<PublishableGroup, 'allow_alliance_posts'> | null): boolean {
    return group?.allow_alliance_posts === false
}

export function post_visibility_value(visibility: FormValue): PostVisibility {
    return visibility === 'members' ? 'members' : 'alliance'
}

export function visibility_field(group_id: number | string) {
    return `visibility_${group_id}`
}

export function announce_field(group_id: number | string) {
    return `announce_${group_id}`
}

export interface PostPublishingInput {
    /** Reads one form field (`FormData.get`). */
    get: (name: string) => FormValue;
    groups: PublishableGroup[];
}

/**
 * What the editor form sends for the publishing row. `host` is "you" (or
 * absent, when the pilot publishes for no group) for an alliance post: that
 * sends nothing, so the request is exactly today's. Editing a group post
 * carries its own group as a hidden `host`, so the host stays as it was.
 */
export function post_publishing_params({ get, groups }: PostPublishingInput): PostPublishingParams {
    const host = String(get('host') ?? HOST_YOU)
    const group_id = parseInt(host)

    if (host === HOST_YOU || isNaN(group_id))
        return {}

    const group = groups.find((candidate) => candidate.id === group_id)
    const members_only = group_forces_members_only(group)
        || post_visibility_value(get(visibility_field(group_id))) === 'members'

    return {
        host_group_id: group_id,
        members_only: members_only,
        announce: (get(announce_field(group_id)) ?? null) !== null,
    }
}

/** Where a group's posts live on its page. */
export function group_posts_href(group: Pick<TribeGroupRefUI, 'tribe_id' | 'id'>): string {
    return `/alliance/tribes/${group.tribe_id}/${group.id}/#posts`
}

/**
 * The text for the Discord switch. The channel name is known only to pilots
 * who can read the guild's channel list, so it falls back to a generic line.
 */
export function announce_hint_key(channel_name: string | null, role_name: string | null, has_channel: boolean) {
    if (!has_channel) return 'tribes.publishing.post.announce_no_channel' as const
    if (channel_name && role_name) return 'tribes.publishing.post.announce_channel_role' as const
    if (channel_name) return 'tribes.publishing.post.announce_channel' as const

    return 'tribes.publishing.post.announce_group_channel' as const
}

export interface GroupDiscordInfo {
    /** False only when the group is known to have no channel to post in. */
    has_channel: boolean;
    channel_name: string | null;
    role_name: string | null;
}

/**
 * Where an announcement would go. The group tells the channel id and role;
 * the channel's name needs the guild channel list, which only some pilots can
 * read, so it may stay unknown. An unfetched group is assumed to have a channel.
 */
export function group_discord_info(group: Pick<TribeGroup, 'effective_discord_channel_id' | 'discord_role_name'> | null, channels: DiscordChannel[]): GroupDiscordInfo {
    if (!group)
        return { has_channel: true, channel_name: null, role_name: null }

    const channel_id = group.effective_discord_channel_id ?? null
    const name = channel_id ? channels.find((channel) => String(channel.id) === String(channel_id))?.name : undefined

    return {
        has_channel: Boolean(channel_id),
        channel_name: name ? (name.startsWith('#') ? name : `#${name}`) : null,
        role_name: group.discord_role_name ?? null,
    }
}
