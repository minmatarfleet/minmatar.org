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
        return { channel_name: null, payload: null, role_name: null, error: false }

    const [preview, group] = await Promise.allSettled([
        preview_fleet_ping(access_token, request),
        group_id && host_tribe_id ? get_tribe_group(host_tribe_id, group_id, access_token) : null,
    ])

    if (preview.status === 'rejected') {
        console.log(`Fleet ping preview: ${preview.reason?.message ?? preview.reason}`)
        return { channel_name: null, payload: null, role_name: null, error: true }
    }

    return {
        channel_name: preview.value.channel_name ?? null,
        payload: preview.value.payload as DiscordPreviewPayloadUI,
        role_name: group.status === 'fulfilled' ? group.value?.discord_role_name ?? null : null,
        error: false,
    }
}
