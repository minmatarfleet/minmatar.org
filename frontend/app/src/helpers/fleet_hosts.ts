// Tribe group fleets on the website: which host a fleet has, who can see it,
// the fleets hub host filter and the fleet form's host fields. Pure, so the
// pages and the tests share one set of rules (docs/tribes/tribe-publishing.md).
import type { FleetTypes, PublishableGroup, FleetPingPreviewRequest } from '@dtypes/api.minmatar.org'
import { fleet_types } from '@dtypes/api.minmatar.org'
import type { TribeGroupRefUI, TribeVisibility } from '@dtypes/layout_components'

interface HostedFleet {
    host_group?:        TribeGroupRefUI | null;
    open_to_alliance?:  boolean;
}

/** Members only or open, for a group fleet; null for an alliance fleet (which never carries a tag). */
export function fleet_visibility(fleet:HostedFleet):TribeVisibility | null {
    if (!fleet.host_group) return null
    return fleet.open_to_alliance ? 'open' : 'members_only'
}

/** The fleet's host as the view model the shared blocks take, from the API's HostGroupRef. */
export function host_group_ref(group:TribeGroupRefUI | null | undefined):TribeGroupRefUI | null {
    if (!group) return null
    return {
        id: group.id,
        code: group.code,
        name: group.name,
        tribe_id: group.tribe_id,
        tribe_name: group.tribe_name,
    }
}

export function tribe_group_path(group:{ id:number, tribe_id:number }, hash:string = '') {
    return `/alliance/tribes/${group.tribe_id}/${group.id}/${hash ? `#${hash}` : ''}`
}

// --- Fleets hub filter -------------------------------------------------------

export const FLEET_HOST_FILTERS = ['all', 'alliance', 'tribe', 'mine'] as const
export type FleetHostFilter = typeof FLEET_HOST_FILTERS[number]

export function parse_host_filter(value:string | null | undefined):FleetHostFilter {
    return (FLEET_HOST_FILTERS as readonly string[]).includes(value ?? '') ? value as FleetHostFilter : 'all'
}

/**
 * Alliance = no host group, Tribe fleets = any host group, My groups = a host
 * group the viewer belongs to. The API already hid the fleets the viewer can't see.
 */
export function filter_fleets_by_host<T extends HostedFleet>(
    fleets:T[],
    filter:FleetHostFilter,
    my_group_ids:Iterable<number> = [],
):T[] {
    if (filter === 'alliance') return fleets.filter(fleet => !fleet.host_group)
    if (filter === 'tribe') return fleets.filter(fleet => fleet.host_group)
    if (filter === 'mine') {
        const mine = new Set(my_group_ids)
        return fleets.filter(fleet => fleet.host_group && mine.has(fleet.host_group.id))
    }
    return fleets
}

export interface FleetHostCounts {
    all:        number;
    alliance:   number;
    tribe:      number;
}

export function count_fleets_by_host<T extends HostedFleet>(fleets:T[]):FleetHostCounts {
    const tribe = fleets.filter(fleet => fleet.host_group).length
    return { all: fleets.length, alliance: fleets.length - tribe, tribe }
}

/** Each host group once, in the order the fleets list them. */
export function fleet_host_groups<T extends HostedFleet>(fleets:T[]):TribeGroupRefUI[] {
    const groups = new Map<number, TribeGroupRefUI>()
    fleets.forEach(fleet => {
        if (fleet.host_group && !groups.has(fleet.host_group.id))
            groups.set(fleet.host_group.id, fleet.host_group)
    })
    return [...groups.values()]
}

// --- Fleet form --------------------------------------------------------------

export const ALLIANCE_HOST = 'alliance'

/** Strategic fleets are alliance only; a group fleet is non-strategic, training or NPSI. */
export function fleet_types_for_host(is_group:boolean):FleetTypes[] {
    return is_group ? fleet_types.filter(type => type !== 'strategic') : [...fleet_types]
}

/** The `?host=` group when the viewer can schedule for it, otherwise null (the form opens on its default). */
export function parse_host_param(value:string | null | undefined, groups:Pick<PublishableGroup, 'id'>[]):number | null {
    const id = parseInt(value ?? '')
    if (!Number.isFinite(id)) return null
    return groups.some(group => group.id === id) ? id : null
}

export interface FleetHostFields {
    host_group_id:      number | null;
    open_to_alliance:   boolean;
    on_schedule:        boolean;
}

interface FormValues {
    get(name:string):FormDataEntryValue | null;
}

/**
 * The host fields of a submitted fleet form, or null when the form had no
 * Host row (the request then leaves them out, as before). `open_to_alliance`
 * only counts for a group that allows open fleets and `on_schedule` only for
 * an open fleet; the API enforces the same. A group missing from `groups`
 * (an FC editing a fleet of a group they no longer publish for) keeps the
 * submitted switches and the API decides.
 */
export function fleet_host_fields(
    data:FormValues,
    groups:Pick<PublishableGroup, 'id' | 'allow_open_fleets'>[],
):FleetHostFields | null {
    const host = data.get('host')
    if (host === null) return null

    const host_group_id = host === ALLIANCE_HOST ? null : parseInt(String(host))
    if (host_group_id === null || !Number.isFinite(host_group_id))
        return { host_group_id: null, open_to_alliance: false, on_schedule: false }

    const group = groups.find(group => group.id === host_group_id)
    const allow_open = group ? group.allow_open_fleets : true
    const open_to_alliance = allow_open && data.get('open_to_alliance') === 'on'
    return {
        host_group_id,
        open_to_alliance,
        on_schedule: open_to_alliance && data.get('on_schedule') === 'on',
    }
}

const int_or_null = (value:FormDataEntryValue | null) => {
    const parsed = parseInt(String(value ?? ''))
    return Number.isFinite(parsed) ? parsed : null
}

/** The ping preview request for the fleet form's current fields. */
export function ping_preview_request(data:FormValues):FleetPingPreviewRequest {
    const host = data.get('host')
    const host_group_id = host && host !== ALLIANCE_HOST ? int_or_null(host) : null
    const type = String(data.get('fleet_type') ?? '')
    const allowed = fleet_types_for_host(host_group_id !== null) as string[]

    return {
        type: (allowed.includes(type) ? type : allowed[0]) as FleetTypes,
        description: String(data.get('description') ?? ''),
        objective: String(data.get('objective') ?? '') || null,
        location_id: int_or_null(data.get('location_id')),
        audience_id: host_group_id === null ? int_or_null(data.get('audience_id')) : null,
        host_group_id,
    }
}
