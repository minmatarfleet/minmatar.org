import type { FleetItem, DoctrineType } from '@dtypes/layout_components'
import type { FleetCommanderMetrics } from '@dtypes/api.minmatar.org'
import { fetch_fleets_auth } from '@helpers/fetching/fleets'
import { fetch_doctrine_by_id } from '@helpers/fetching/doctrines'
import { get_characters_summary_sorted } from '@helpers/fetching/characters'
import { get_fleet_commander_metrics, get_fleet_ship_volunteers, get_fleet_results, type FleetResult } from '@helpers/api.minmatar.org/fleets'
import { unique_values } from '@helpers/array'
import { fleet_phase } from '@helpers/fleet_phase'

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
}

const is_live = (fleet:FleetItem) => fleet_phase(fleet) === 'active'

export async function fetch_fleet_schedule(auth_token:string):Promise<FleetSchedule> {
    const fc_metrics = await get_fleet_commander_metrics(auth_token)
    const fleets = await fetch_fleets_auth(auth_token, true, false, fc_metrics)
    fleets.sort((a, b) => new Date(a.start_time).getTime() - new Date(b.start_time).getTime())

    const live = fleets.filter(is_live)
    const next = fleets.find(fleet => !is_live(fleet) && fleet.status !== 'cancelled') ?? null
    const featured = new Set([ ...live.map(fleet => fleet.id), next?.id ])
    const rest = fleets.filter(fleet => !featured.has(fleet.id))

    const doctrines = await fetch_doctrine_names(fleets)

    let next_signups = 0
    if (next) {
        try {
            const [summary, volunteers] = await Promise.all([
                get_characters_summary_sorted(auth_token),
                get_fleet_ship_volunteers(auth_token, next.id),
            ])
            const mine = new Set((summary.characters ?? []).map(character => character.character_id))
            next_signups = volunteers.filter(volunteer => mine.has(volunteer.character_id)).length
        } catch (error) {
            console.log(`Skipping next fleet signups: ${error.message}`)
        }
    }

    return { fleets, live, next, rest, doctrines, next_signups, fc_metrics }
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

export async function fetch_fleet_history(auth_token:string):Promise<FleetHistory> {
    const fc_metrics = await get_fleet_commander_metrics(auth_token)
    const fleets = await fetch_fleets_auth(auth_token, false, false, fc_metrics)
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
