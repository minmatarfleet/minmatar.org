import { group_by } from '@helpers/array';
import type {
    BaseIndustryOrder,
    IndustryOrder,
    Producer,
    PlanetWithColoniesItem,
    OrderAssignmentsBreakdownItem,
    RootItem
} from '@dtypes/api.minmatar.org'
import type { OrderLocation, ColonySystems, ColonyPlanet, OrderBreakdownUI, IndustryOrderUI } from '@dtypes/layout_components'
import {
    get_orders_summary_flat,
    get_orders_summary_nested,
    get_orders_with_location,
    get_blueprints,
    get_planetary_planets,
    get_order_by_id,
    get_order_assignments_breakdown,
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

function get_children_materials(childrens:OrderAssignmentsBreakdownItem[]) {
    let materials:RootItem[] = []
    let copy_breakdown = ''

    childrens.forEach(children => {
        const tabs = '\t'.repeat(children.depth)
        copy_breakdown = copy_breakdown.concat(`${tabs}${children.name}\t${children.quantity}\n`)

        if (children.children.length === 0) {
            materials.push({
                eve_type_id: children.type_id,
                eve_type_name: children.name,
                quantity: children.quantity
            })
        } else {
            const children_breakdown = get_children_materials(children.children)

            materials = [ ...materials, ...children_breakdown.children_materials ]
            copy_breakdown = copy_breakdown.concat(children_breakdown.children_copy_breakdown)
        }
    })

    return {
        children_materials: materials,
        children_copy_breakdown: copy_breakdown
    }
}

function deduple_materials(materials:RootItem[]) {
    const materials_by_id:Record<string, RootItem> = {}
    const dedupled_materials:RootItem[] = []

    materials.forEach(material => {
        materials_by_id[material.eve_type_id] = {
            eve_type_id: material.eve_type_id,
            eve_type_name: material.eve_type_name,
            quantity: material.quantity + (materials_by_id[material.eve_type_id]?.quantity ?? 0)
        }
    })

    for (let type_id in materials_by_id)
        dedupled_materials.push(materials_by_id[type_id])

    return dedupled_materials
}

export async function fetch_order_breakdown(order_id: number) {
    const order = await get_order_by_id(order_id)
    const order_breakdown:OrderBreakdownUI[] = []

    await Promise.all(order?.items.map(async (item) => {
        const assignments_breakdown = (await get_order_assignments_breakdown(order_id, item.id))?.assignments ?? []

        assignments_breakdown.map(assignment => {            
            const breakdown = assignment.breakdown
            let materials:RootItem[] = [{
                eve_type_id: breakdown.type_id,
                eve_type_name: breakdown.name,
                quantity: breakdown.quantity,
            }]
            let copy_breakdown = `${breakdown.quantity}×${breakdown.name}\n`

            const { children_materials, children_copy_breakdown } = get_children_materials(breakdown.children)

            order_breakdown.push({
                character_id: assignment.character_id,
                character_name: assignment.character_name,
                quantity: assignment.quantity,
                type_id: item.eve_type_id,
                name: item.eve_type_name,
                materials: deduple_materials([ ...materials, ...children_materials ]),
                copy_breakdown: copy_breakdown.concat(children_copy_breakdown),
            })
        })
    }))

    return order_breakdown
}

export async function fetch_order_breakdown_grouped(order_id: number) {
    const order = await get_order_by_id(order_id)
    return order.items
}

export async function fetch_order_by_id(order_id: number) {
    const order =  await get_order_by_id(order_id)
    const producers:Record<string, Producer> = {}

    order.items.map(character => {
        character.assignments.map(assignment => {
            if (!producers[assignment.character_id]) {
                producers[assignment.character_id] = {
                    id: assignment.character_id,
                    name: assignment.character_name,
                }
            }
        })
    })

    const assigned_to:Producer[] = []
    for (let i in producers)
        assigned_to.push(producers[i])

    return {
        id: order.id,
        character_id: order.character_id,
        character_name: order.character_name,
        created_at: order.created_at,
        fulfilled_at: order.fulfilled_at,
        location: order.location,
        needed_by: order.needed_by,
        items: order.items,
        assigned_to: assigned_to,
    } as IndustryOrderUI
}