import type { IndustryOrderCharacterStatistics } from '@dtypes/api.minmatar.org'
import type { OrderLocation } from '@dtypes/layout_components'
import { get_orders_character_statistics } from '@helpers/api.minmatar.org/industry'
import { fetch_orders_by_locations } from '@helpers/fetching/industry'

export type IndustryOrdersPageData = {
    orders_locations: OrderLocation[]
    fetching_error: Error | false
    manufacturers: IndustryOrderCharacterStatistics[]
}

export async function load_industry_orders_page(
    history: boolean = false,
): Promise<IndustryOrdersPageData> {
    const [orders_result, manufacturers] = await Promise.all([
        fetch_orders_by_locations(history)
            .then((data) => ({ data, error: false as const }))
            .catch((error: Error) => ({
                data: [] as OrderLocation[],
                error,
            })),
        get_orders_character_statistics().catch((error) => {
            console.log(error)
            return [] as IndustryOrderCharacterStatistics[]
        }),
    ])

    return {
        orders_locations: orders_result.data,
        fetching_error:
            orders_result.error === false ? false : orders_result.error,
        manufacturers,
    }
}
