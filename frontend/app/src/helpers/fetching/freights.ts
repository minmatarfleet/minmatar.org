import type { FreightRoutesData } from '@dtypes/layout_components'
import type { FreightContract } from '@dtypes/api.minmatar.org'

import { get_routes, get_contracts } from '@helpers/api.minmatar.org/freights'

const STATUS_SORT_ORDER: Record<string, number> = {
    outstanding: 0,
    in_progress: 1,
    finished: 2,
}

export function freight_route_label(start: string, end: string): string {
    return `${start} → ${end}`
}

export async function fetch_freight_routes() {
    const api_freight_routes = await get_routes()
    const freight_routes_data: FreightRoutesData = {
        routes: [],
        route_translation: {},
        stations: {},
        route_details: {},
    }

    for (const api_freight_route of api_freight_routes) {
        const normal_route_id = `${api_freight_route.orgin.location_id}-${api_freight_route.destination.location_id}`
        freight_routes_data.route_translation[normal_route_id] = api_freight_route.route_id
        freight_routes_data.routes.push({
            label: `${api_freight_route.orgin.short_name} → ${api_freight_route.destination.short_name}`,
            value: normal_route_id
        })
        freight_routes_data.stations[normal_route_id] = [api_freight_route.orgin.name, api_freight_route.destination.name]
        freight_routes_data.route_details[normal_route_id] = {
            expiration_days: api_freight_route.expiration_days,
            days_to_complete: api_freight_route.days_to_complete,
            collateral_modifier: api_freight_route.collateral_modifier ?? 0,
            route_type: api_freight_route.route_type ?? 'rate',
            max_m3: api_freight_route.max_m3 ?? 350000,
            max_collateral: api_freight_route.max_collateral ?? null,
        }
    }

    return freight_routes_data
}

export async function fetch_freight_contracts(history: boolean = false): Promise<FreightContract[]> {
    const contracts = await get_contracts(history)
    const valid_contracts = contracts.filter(contract => contract.issuer_id > 0)

    return valid_contracts.sort((a, b) => {
        const status_diff = (STATUS_SORT_ORDER[a.status] ?? 99) - (STATUS_SORT_ORDER[b.status] ?? 99)
        if (status_diff !== 0)
            return status_diff

        const a_date = new Date(a.status === 'finished' ? (a.date_completed ?? a.date_issued) : a.date_issued).getTime()
        const b_date = new Date(b.status === 'finished' ? (b.date_completed ?? b.date_issued) : b.date_issued).getTime()
        return b_date - a_date
    })
}

export function filter_freight_contracts_by_location(
    contracts: FreightContract[],
    location_name: string | null,
): FreightContract[] {
    if (!location_name)
        return contracts

    const needle = location_name.toLowerCase()

    return contracts.filter(contract => {
        const start = contract.start_location_name.toLowerCase()
        const end = contract.end_location_name.toLowerCase()

        return (
            needle.includes(start)
            || needle.includes(end)
            || start.includes(needle)
            || end.includes(needle)
        )
    })
}
