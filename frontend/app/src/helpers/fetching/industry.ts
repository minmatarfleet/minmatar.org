import { group_by } from '@helpers/array';
import type { BaseIndustryOrder, IndustryOrder, Producer, PlanetWithColoniesItem } from '@dtypes/api.minmatar.org'
import type { OrderLocation, ColonySystems, ColonyPlanet } from '@dtypes/layout_components'
import {
    get_orders_summary_flat,
    get_orders_summary_nested,
    get_orders_with_location,
    get_blueprints,
    get_planetary_planets,
} from '@helpers/api.minmatar.org/industry'
import { get_system_name, get_system_sun_type_id, get_planet_info } from '@helpers/sde/map'

export async function fetch_orders_summary_flat() {
    const orders = await get_orders_summary_flat()

    return (orders?.items ?? []) as BaseIndustryOrder[]
}

export async function fetch_orders_summary() {
    const orders = await get_orders_summary_nested()
    return orders.roots ?? []
}

export async function fetch_orders_by_locations() {
    const orders = await get_orders_with_location()
    let orders_by_locations: Record<string, IndustryOrder[]> = {}
    let orders_locations:OrderLocation[] = []

    orders.forEach(order => {
        if (!order.location) return true

        if (!orders_by_locations[order.location.location_id.toString()])
            orders_by_locations[order.location.location_id.toString()] = []

        orders_by_locations[order.location.location_id.toString()].push(order)
    })

    for (let location_id in orders_by_locations) {
        const location_orders = orders_by_locations[location_id]

        orders_locations.push({
            location_id: location_orders[0].location.location_id,
            location_name: location_orders[0].location.location_name,
            orders: location_orders.map(order => {
                return {
                    id: order.id,
                    character_id: order.character_id,
                    character_name: order.character_name,
                    created_at: order.created_at,
                    fulfilled_at: order.fulfilled_at,
                    location: order.location,
                    needed_by: order.needed_by,
                    items: order.items,
                    assigned_to: order.assigned_to.map(character => {
                        return {
                            id: character.character_id,
                            name: character.character_name,
                        } as Producer
                    }),
                }
            }),
        })
    }

    return orders_locations
}

export async function fetch_blueprints(is_copy:boolean = false) {
    let blueprints = await get_blueprints(is_copy)
    blueprints = blueprints.map(blueprint => {
        blueprint.location_flag = blueprint.location_flag.startsWith('CorpSAG') ? 'CorpSAG' : blueprint.location_flag
        return blueprint
    })

    return blueprints
}

export async function fetch_colonies() {
    const planet_list = await get_planetary_planets()
    const colonies:ColonySystems[] = []

    const colonies_by_solar_system:Record<string, PlanetWithColoniesItem[]> = group_by(planet_list, 'solar_system_id')

    for (let solar_system_id in colonies_by_solar_system) {
        const system_id = parseInt(solar_system_id)
        
        const planets = await Promise.all(colonies_by_solar_system[solar_system_id].map(async (planet) => {
            const planet_info = await get_planet_info(planet.planet_id)

            return {
                planet_id: planet.planet_id,
                planet_name: planet_info?.name ?? `${planet.planet_id}`,
                planet_type: planet.planet_type,
                planet_type_id: planet_info?.type_id ?? 0,
                colonies: planet.colonies,
            } as ColonyPlanet
        }))

        planets.sort((a, b) => a.planet_name.localeCompare(b.planet_name))

        colonies.push({
            solar_system_id: system_id,
            solar_system_name: await get_system_name(system_id) ?? `''`,
            system_sun_type_id: await get_system_sun_type_id(system_id) ?? 0,
            planets: planets,
        })
    }

    colonies.sort((a, b) => a.solar_system_name.localeCompare(b.solar_system_name))

    return colonies
}