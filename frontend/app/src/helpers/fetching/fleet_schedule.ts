import type { FleetItem, DoctrineType } from '@dtypes/layout_components'
import type { FleetCommanderMetrics } from '@dtypes/api.minmatar.org'
import { fetch_fleets_auth } from '@helpers/fetching/fleets'
import { fetch_doctrine_by_id } from '@helpers/fetching/doctrines'
import { get_characters_summary_sorted } from '@helpers/fetching/characters'
import { get_fleet_commander_metrics, get_fleet_ship_volunteers, get_fleet_results, type FleetResult } from '@helpers/api.minmatar.org/fleets'
import { unique_values } from '@helpers/array'
import { fleet_phase } from '@helpers/fleet_phase'
import { get_tribe_group } from '@helpers/api.minmatar.org/tribes'
import {
    count_fleets_by_host,
    filter_fleets_by_host,
    fleet_host_groups,
    type FleetHostCounts,
    type FleetHostFilter,
} from '@helpers/fleet_hosts'

export interface FleetScheduleDoctrine {
    name:       string;
    ship_id:    number | null;
}

export interface FleetSchedule {
    fleets:         FleetItem[];
    /** Tracking started and not ended. */
    live:           FleetItem[];
    /** The first scheduled fleet that is not live or cancelled. */
    next:           FleetItem | null;
    /** Everything else, in start order. The live and next fleets are not repeated here. */
    rest:           FleetItem[];
    doctrines:      Record<number, FleetScheduleDoctrine>;
    /** How many of the viewer's characters are signed up for the next fleet. */
    next_signups:   number;
    fc_metrics:     FleetCommanderMetrics[];
    /** The host filter applied to `fleets` (All · Alliance · Tribe fleets · My groups). */
    host_filter:    FleetHostFilter;
    /** Counted before the host filter; `tribe` is 0 when the viewer sees no group fleets. */
    host_counts:    FleetHostCounts;
}

const is_live = (fleet:FleetItem) => fleet_phase(fleet) === 'active'

/**
 * Waits for both, then throws the first one's error before the second's: the
 * FC metrics used to be fetched before the fleets, so when both fail the
 * error shown stays the same.
 */
async function settled_in_order<A, B>(first:Promise<A>, second:Promise<B>):Promise<[A, B]> {
    const [a, b] = await Promise.allSettled([first, second])
    if (a.status === 'rejected')
        throw a.reason
    if (b.status === 'rejected')
        throw b.reason
    return [a.value, b.value]
}

export async function fetch_fleet_schedule(auth_token:string, host_filter:FleetHostFilter = 'all'):Promise<FleetSchedule> {
    // The FC metrics are requested together with the fleets (fetch_fleets_auth
    // starts the fleets and their metrics at the same time).
    const fc_metrics_promise = get_fleet_commander_metrics(auth_token)
    fc_metrics_promise.catch(() => null)
    const [fc_metrics, all_fleets] = await settled_in_order(
        fc_metrics_promise,
        fetch_fleets_auth(auth_token, true, false, fc_metrics_promise),
    )
    all_fleets.sort((a, b) => new Date(a.start_time).getTime() - new Date(b.start_time).getTime())

    const host_counts = count_fleets_by_host(all_fleets)
    const my_group_ids = host_filter === 'mine' ? await fetch_my_group_ids(auth_token, all_fleets) : []
    const fleets = filter_fleets_by_host(all_fleets, host_filter, my_group_ids)

    const live = fleets.filter(is_live)
    const next = fleets.find(fleet => !is_live(fleet) && fleet.status !== 'cancelled') ?? null
    const featured = new Set([ ...live.map(fleet => fleet.id), next?.id ])
    const rest = fleets.filter(fleet => !featured.has(fleet.id))

    // The doctrine names and the next fleet's signups don't depend on each
    // other; each still handles its own failures as before.
    const [doctrines, next_signups] = await Promise.all([
        fetch_doctrine_names(fleets),
        next ? fetch_next_signups(auth_token, next.id) : Promise.resolve(0),
    ])

    return { fleets, live, next, rest, doctrines, next_signups, fc_metrics, host_filter, host_counts }
}

/** How many of the viewer's characters signed up for this fleet; 0 if either call fails. */
async function fetch_next_signups(auth_token:string, fleet_id:number):Promise<number> {
    try {
        const [summary, volunteers] = await Promise.all([
            get_characters_summary_sorted(auth_token),
            get_fleet_ship_volunteers(auth_token, fleet_id),
        ])
        const mine = new Set((summary.characters ?? []).map(character => character.character_id))
        return volunteers.filter(volunteer => mine.has(volunteer.character_id)).length
    } catch (error) {
        console.log(`Skipping next fleet signups: ${error.message}`)
        return 0
    }
}

/**
 * The host groups on these fleets that the viewer is an active member of.
 * Only the groups the list names are asked about, so it is a call or two.
 */
export async function fetch_my_group_ids(auth_token:string, fleets:FleetItem[]):Promise<number[]> {
    const groups = await Promise.all(fleet_host_groups(fleets).map(async group => {
        try {
            const tribe_group = await get_tribe_group(group.tribe_id, group.id, auth_token)
            return tribe_group.is_member ? group.id : null
        } catch (error) {
            console.log(`Skipping group ${group.id} membership: ${error.message}`)
            return null
        }
    }))
    return groups.filter((id):id is number => id !== null)
}

/** Name and lead hull of each doctrine the fleets use; a doctrine that fails to load is left out. */
export async function fetch_doctrine_names(fleets:FleetItem[]):Promise<Record<number, FleetScheduleDoctrine>> {
    const doctrine_ids = unique_values(fleets.map(fleet => fleet.doctrine_id).filter(Boolean)) as number[]
    const fetched = await Promise.all(doctrine_ids.map(async id => {
        try {
            return await fetch_doctrine_by_id(id)
        } catch (error) {
            console.log(`Skipping doctrine ${id}: ${error.message}`)
            return null
        }
    }))
    const doctrines:Record<number, FleetScheduleDoctrine> = {}
    fetched.forEach((doctrine:DoctrineType | null) => {
        if (doctrine)
            doctrines[doctrine.id] = {
                name: doctrine.name,
                ship_id: doctrine.primary_fittings?.[0]?.ship_id ?? null,
            }
    })
    return doctrines
}

export { eve_day, eve_clock } from '@helpers/date'

export interface FleetHistory {
    /** Fleets that tracked, newest first. */
    tracked:        FleetItem[];
    /** Scheduled fleets that never started tracking. */
    untracked:      FleetItem[];
    doctrines:      Record<number, FleetScheduleDoctrine>;
    results:        Record<number, FleetResult>;
    fc_metrics:     FleetCommanderMetrics[];
}

/** `host_group_id` narrows the history to one tribe group's fleets. */
export async function fetch_fleet_history(auth_token:string, host_group_id:number | null = null):Promise<FleetHistory> {
    const fc_metrics_promise = get_fleet_commander_metrics(auth_token)
    fc_metrics_promise.catch(() => null)
    const [fc_metrics, fleets] = await settled_in_order(
        fc_metrics_promise,
        fetch_fleets_auth(auth_token, false, false, fc_metrics_promise, host_group_id),
    )
    const started = (fleet:FleetItem) => new Date(fleet.tracking?.start_time ?? fleet.start_time).getTime()
    fleets.sort((a, b) => started(b) - started(a))

    // A live fleet belongs on the fleets page, not in history.
    const tracked = fleets.filter(fleet => fleet.tracking?.end_time)
    const untracked = fleets.filter(fleet => !fleet.tracking && fleet.status !== 'cancelled')

    const [ doctrines, results ] = await Promise.all([
        fetch_doctrine_names(tracked),
        get_fleet_results(auth_token, tracked.map(fleet => fleet.id)).catch(error => {
            console.log(`Skipping fleet results: ${error.message}`)
            return [] as FleetResult[]
        }),
    ])

    return {
        tracked,
        untracked,
        doctrines,
        results: Object.fromEntries(results.map(result => [ result.fleet_id, result ])),
        fc_metrics,
    }
}
