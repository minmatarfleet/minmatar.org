import type {
    IndustryOrder,
    Producer,
    OrderAssignmentsBreakdownItem,
    RootItem
} from '@dtypes/api.minmatar.org'
import type { OrderLocation, OrderBreakdownUI, IndustryOrderUI } from '@dtypes/layout_components'
import {
    get_orders_with_location,
    get_blueprints,
    get_order_by_id,
    get_order_orderitems,
    get_order_assignments_breakdown,
} from '@helpers/api.minmatar.org/industry'

export async function fetch_orders_by_locations(history:boolean = false) {
    const api_orders = await get_orders_with_location()
    const orders = api_orders.filter(order => history ? order.fulfilled_at : !order.fulfilled_at)
    
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
                    public_short_code: order.public_short_code,
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

export async function fetch_blueprints(query:string, is_copy:boolean = false) {
    let blueprints = await get_blueprints(query, is_copy)
    blueprints = blueprints.map(blueprint => {
        blueprint.location_flag = blueprint.location_flag.startsWith('CorpSAG') ? 'CorpSAG' : blueprint.location_flag
        return blueprint
    })

    return blueprints
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
    // Use orderitems only — full GET /orders/{id} runs BOM planning for
    // coordinator options and is far too slow for this partial.
    return await get_order_orderitems(order_id)
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
        public_short_code: order.public_short_code,
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