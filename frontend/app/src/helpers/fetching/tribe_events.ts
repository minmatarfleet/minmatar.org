import type { DiscordChannel, TribeEvent, TribeGroup } from '@dtypes/api.minmatar.org'
import type { DiscordChannelUI } from '@dtypes/layout_components'
import { get_discord_channels, get_group_events, get_tribe_group } from '@helpers/api.minmatar.org/tribes'
import { discord_channel_ui } from '@helpers/tribe_group_page'

export interface TribeEventFormContext {
    group:              TribeGroup;
    voice_channels:     DiscordChannelUI[];
    /** False when the voice channel list did not load. */
    voice_channels_ok:  boolean;
    /** The group's effective text channel (its own, or the tribe's), when the list loaded. */
    channel_name:       string | null;
}

/** What the event form needs: the host group, voice channels for Where, and the announcement channel's name. */
export async function fetch_tribe_event_form_context(
    access_token: string,
    tribe_id: number,
    group_id: number,
): Promise<TribeEventFormContext> {
    const group = await get_tribe_group(tribe_id, group_id, access_token)
    const [voice, text] = await Promise.all([
        get_discord_channels(access_token, 'voice').then((list) => list.map(discord_channel_ui)).catch(() => null),
        group.effective_discord_channel_id
            ? get_discord_channels(access_token, 'text').catch((): DiscordChannel[] => [])
            : Promise.resolve<DiscordChannel[]>([]),
    ])
    const channel = text.find((item) => item.id === group.effective_discord_channel_id)
    return {
        group,
        voice_channels: voice ?? [],
        voice_channels_ok: voice !== null,
        channel_name: channel?.name ?? null,
    }
}

/** One of the group's upcoming events (there is no single-event endpoint), or null. */
export async function fetch_group_event(
    access_token: string,
    group_id: number,
    event_id: number,
): Promise<TribeEvent | null> {
    const events = await get_group_events(group_id, access_token)
    return events.find((event) => event.id === event_id) ?? null
}
