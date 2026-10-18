import type { DiscordChannel, PublishableGroup } from '@dtypes/api.minmatar.org'
import type { HostOptionUI } from '@dtypes/layout_components'
import { get_discord_channels, get_publishable_groups, get_tribe_group } from '@helpers/api.minmatar.org/tribes'
import { get_user_character } from '@helpers/fetching/characters'
import { get_player_icon } from '@helpers/eve_image_server'
import { i18n } from '@helpers/i18n'
import { can, type GateContext } from '@helpers/gates'
import { group_discord_info, post_host_options, type GroupDiscordInfo } from '@helpers/post_publishing'

/** The tribe groups the pilot may post as. Empty on any error: the row simply doesn't show. */
export async function get_post_publishable_groups(access_token?:string | false | null) {
    if (!access_token) return [] as PublishableGroup[]

    try {
        return await get_publishable_groups(access_token, 'post')
    } catch {
        return [] as PublishableGroup[]
    }
}

/**
 * Whether the pilot has their own posts to manage: the alliance `posts.create`
 * gate, or posting as a group they publish for (which needs no `posts.create`).
 */
export async function can_manage_own_posts(gates:GateContext, access_token?:string | false | null) {
    if (can(gates, 'posts.create')) return true

    return (await get_post_publishable_groups(access_token)).length > 0
}

type Translate = ReturnType<typeof i18n>['t']

export interface PublishAsContext {
    hosts: HostOptionUI[];
    discord_by_group: Record<number, GroupDiscordInfo>;
}

/**
 * What the "Publish as" row needs: the host cards ("You" first) and, per group,
 * where its Discord announcement would go. Every lookup is best effort; a miss
 * leaves a generic hint rather than blocking the editor.
 */
export async function get_publish_as_context(args: {
    access_token: string;
    user_id: number;
    groups: PublishableGroup[];
    /** Only these groups' Discord details are fetched (the picked one, or the post's host). */
    discord_group_ids?: number[];
    t: Translate;
}): Promise<PublishAsContext> {
    const { access_token, user_id, groups, discord_group_ids, t } = args

    let you_image = '/images/fleet-logo-square.svg'
    let you_label: string = t('tribes.publishing.post.you_label')
    try {
        const character = await get_user_character(user_id)
        if (character?.character_id) {
            you_image = get_player_icon(character.character_id, 64)
            you_label = character.character_name
        }
    } catch {}

    const hosts = post_host_options(
        groups,
        { label: you_label, sub: t('tribes.publishing.post.you_sub'), image_url: you_image },
        (group) => t('tribes.publishing.post.group_sub')
            .replace('{tribe}', group.tribe_name)
            .replace('{count}', String(group.member_count)),
    )

    const discord_groups = groups.filter((group) => !discord_group_ids || discord_group_ids.includes(group.id))
    const discord_by_group: Record<number, GroupDiscordInfo> = {}

    if (discord_groups.length > 0) {
        const channels = await get_discord_channels(access_token, 'text').catch(() => [] as DiscordChannel[])

        await Promise.all(discord_groups.map(async (group) => {
            const tribe_group = await get_tribe_group(group.tribe_id, group.id, access_token).catch(() => null)
            discord_by_group[group.id] = group_discord_info(tribe_group, channels)
        }))
    }

    return { hosts, discord_by_group }
}
