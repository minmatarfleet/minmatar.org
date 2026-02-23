import type { BaseIndustryOrder, IndustryOrder, Producer } from '@dtypes/api.minmatar.org'
import type { OrderLocation } from '@dtypes/layout_components'
import { get_orders_summary_flat, get_orders_summary_nested, get_orders_with_location } from '@helpers/api.minmatar.org/industry'

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