import { useTranslations } from '@i18n/utils';
const t = useTranslations('en');

import type { FreightRoutesData } from '@dtypes/layout_components'
import type { FreightRoute, } from '@dtypes/api.minmatar.org'

import { get_routes, get_route_options } from '@helpers/api.minmatar.org/freights'

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