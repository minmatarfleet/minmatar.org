import type {
    IndustryOrder,
    Producer,
} from '@dtypes/api.minmatar.org'
import type { OrderLocation, IndustryOrderUI } from '@dtypes/layout_components'
import {
    get_orders_with_location,
    get_blueprints,
    get_order_by_id,
    get_order_orderitems,
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

        // Orders without a location were left out above.
        const location = location_orders[0].location!

        orders_locations.push({
            location_id: location.location_id,
            location_name: location.location_name,
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