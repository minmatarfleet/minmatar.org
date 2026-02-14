import type { BaseIndustryOrder } from '@dtypes/api.minmatar.org'
import { get_orders_summary_flat, get_orders_summary_nested } from '@helpers/api.minmatar.org/industry'

export async function fetch_orders_summary_flat() {
    const orders = await get_orders_summary_flat()

    return (orders?.items ?? []) as BaseIndustryOrder[]
}

export async function fetch_orders_summary() {
    const orders = await get_orders_summary_nested()
    return orders.roots ?? []
}