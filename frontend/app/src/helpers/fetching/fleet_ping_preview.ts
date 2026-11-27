import type { FleetPingPreviewRequest } from '@dtypes/api.minmatar.org'
import type { DiscordPreviewPayloadUI } from '@dtypes/layout_components'
import { preview_fleet_ping } from '@helpers/api.minmatar.org/fleets'
import { get_tribe_group } from '@helpers/api.minmatar.org/tribes'

export interface FleetPingPreviewUI {
    channel_name:   string | null;
    payload:        DiscordPreviewPayloadUI | null;
    /** The group role the ping mentions (`@Tribe Group - Dreads`); null for alliance pings or when unknown. */
    role_name:      string | null;
    error:          boolean;
    /** Why a group fleet's start ping would reach nobody; null when it will ping. */
    warning:        FleetPingWarning;
    /** Corporations whose own Discord also gets the start ping (with @here). */
    also_posted_to: string[];
}

export type FleetPingWarning = 'no_channel' | 'no_role' | null

/** "Also posted with @here to M-EXC." for the corporations that follow the
 * group, or '' when none do. `template` has a `{names}` placeholder. */
export function also_posted_to_line(names: string[] | null | undefined, template: string): string {
    return names?.length ? template.replace('{names}', names.join(', ')) : ''
}

/**
 * A group fleet pings the group's role in its channel (build_start_ping).
 * Without a channel nothing is sent; without a linked role the message
 * mentions nobody. Alliance fleets always ping their audience's channel.
 * `has_channel` comes from the backend, not the channel's name: the name
 * can be unknown (Discord unreachable, channel not cached) while the ping
 * still goes out.
 */
export function ping_preview_warning(
    host_group:boolean,
    has_channel:boolean,
    content:string | null | undefined,
):FleetPingWarning {
    if (!host_group) return null
    if (!has_channel) return 'no_channel'
    if (!content?.includes('<@&')) return 'no_role'
    return null
}

/**
 * The start ping the fleet form would send, from the backend's own builder.
 * Never throws: a failed preview renders an empty card with a note.
 * `host_tribe_id` lets it name the group's role (the payload only has its id).
 */
export async function fetch_fleet_ping_preview(
    access_token:string,
    request:FleetPingPreviewRequest,
    host_tribe_id:number | null = null,
):Promise<FleetPingPreviewUI> {
    const group_id = request.host_group_id ?? null
    // An alliance fleet with no audience picked yet has no channel to preview.
    if (!group_id && !request.audience_id)
        return { channel_name: null, payload: null, role_name: null, error: false, warning: null, also_posted_to: [] }

    const [preview, group] = await Promise.allSettled([
        preview_fleet_ping(access_token, request),
        group_id && host_tribe_id ? get_tribe_group(host_tribe_id, group_id, access_token) : null,
    ])

    if (preview.status === 'rejected') {
        console.log(`Fleet ping preview: ${preview.reason?.message ?? preview.reason}`)
        return { channel_name: null, payload: null, role_name: null, error: true, warning: null, also_posted_to: [] }
    }

    const channel_name = preview.value.channel_name ?? null
    // A backend older than has_channel: fall back to the resolved name.
    const has_channel = preview.value.has_channel ?? Boolean(channel_name)
    const payload = preview.value.payload as DiscordPreviewPayloadUI
    return {
        channel_name,
        payload,
        role_name: group.status === 'fulfilled' ? group.value?.discord_role_name ?? null : null,
        error: false,
        warning: ping_preview_warning(Boolean(group_id), has_channel, payload?.content),
        // A backend older than corporation follows sends none.
        also_posted_to: preview.value.also_posted_to ?? [],
    }
}
