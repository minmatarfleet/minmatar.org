import { useTranslations } from '@i18n/utils';
const t = useTranslations('en');

import type { FreightRoutesData, FreightContractLocation } from '@dtypes/layout_components'
import type { FreightRoute, FreightContract } from '@dtypes/api.minmatar.org'

import { get_routes, get_route_options, get_contracts } from '@helpers/api.minmatar.org/freights'

import { number_thousand_separator } from '@helpers/numbers'

export async function fetch_freight_routes() {
    let api_freight_routes:FreightRoute[]
    let freight_routes_data:FreightRoutesData = {
        routes: [],
        sizes: {},
        route_translation: {},
        stations: {},
    }

    api_freight_routes = await get_routes()

    await Promise.all(api_freight_routes.map(async (api_freight_route, index) => {
        try {
            const route_options = await get_route_options(api_freight_route.route_id)
            const normal_route_id = `${api_freight_route.orgin.location_id}-${api_freight_route.destination.location_id}`
            freight_routes_data.route_translation[normal_route_id] = api_freight_route.route_id
            
            freight_routes_data.routes.push({
                label: `${api_freight_route.orgin.short_name} → ${api_freight_route.destination.short_name}`,
                value: normal_route_id
            })

            freight_routes_data.sizes[normal_route_id] = []
            route_options.map( (option) => {
                freight_routes_data.sizes[normal_route_id].push({
                    label: number_thousand_separator(option.maximum_m3),
                    value: option.route_option_id,
                })

                freight_routes_data.stations[normal_route_id] = [ api_freight_route.orgin.name, api_freight_route.destination.name ]
            })

            if (api_freight_route.bidirectional) {
                const reverse_route_id = `${api_freight_route.destination.location_id}-${api_freight_route.orgin.location_id}`
                freight_routes_data.route_translation[reverse_route_id] = api_freight_route.route_id

                freight_routes_data.routes.push({
                    label: `${api_freight_route.destination.short_name} → ${api_freight_route.orgin.short_name}`,
                    value: reverse_route_id
                })

                freight_routes_data.sizes[reverse_route_id] = freight_routes_data.sizes[normal_route_id]

                freight_routes_data.stations[reverse_route_id] = [ api_freight_route.destination.name, api_freight_route.orgin.name ]
            }
        } catch (error) {
            console.log(error)
        }
    } ))

    return freight_routes_data
}

export async function fetch_freight_contracts(history:boolean = false) {
    const contracts = await get_contracts(history)
    const valid_contracts = contracts.filter(contract => contract.issuer_id > 0)
    const routes: Record<string, Record<string, FreightContract[]>> = {}
    const contracts_by_locations:FreightContractLocation[] = []
    
    valid_contracts.forEach(contract => {
        const start_location_name = contract.start_location_name
        const end_location_name = contract.end_location_name

        if (!routes[start_location_name]) routes[start_location_name] = {}
        if (!routes[start_location_name][end_location_name]) routes[start_location_name][end_location_name] = []

        routes[start_location_name][end_location_name].push(contract)
    })

    for (let start_location_name in routes) {
        const route_contracts_by_end_location_name = routes[start_location_name]
        const location:FreightContractLocation = {
            location_name: start_location_name,
            destinations: [],
        }

        for (let end_location_name in route_contracts_by_end_location_name) {
            const route_contracts = route_contracts_by_end_location_name[end_location_name]

            location.destinations.push({
                location_name: end_location_name,
                contracts: route_contracts,
            })
        }

        contracts_by_locations.push(location)
    }

    return contracts_by_locations
}