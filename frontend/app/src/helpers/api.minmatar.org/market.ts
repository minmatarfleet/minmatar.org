import type {
    Contract,
    ContractMetrics,
    InferredSalesMonthlyVolumePage,
    LiveSellOrderSupply,
    MarketHealth,
    MarketOperatorStatistics,
} from '@dtypes/api.minmatar.org'
import { api_request } from '@helpers/api.minmatar.org/client'

const API_ENDPOINT =  `${import.meta.env.API_URL}/api/market`

export async function get_market_contracts(location_id: number) {
    const ENDPOINT = `${API_ENDPOINT}/contracts?location_id=${location_id}`

    return await api_request<Contract[]>(ENDPOINT, {
        error: 'Error fetching contracts',
    })
}

export async function get_market_contracts_metrics(location_id: number) {
    const ENDPOINT = `${API_ENDPOINT}/contracts/metrics?location_id=${location_id}`

    return await api_request<ContractMetrics[]>(ENDPOINT, {
        error: 'Error fetching contract metrics',
    })
}

export async function get_market_health(
    location_id: number,
    options: { days?: number } = { days: 30 },
) {
    const params = new URLSearchParams()
    params.set('location_id', String(location_id))
    if (options.days != null)
        params.set('days', String(options.days))

    const ENDPOINT = `${API_ENDPOINT}/health?${params.toString()}`

    return await api_request<MarketHealth>(ENDPOINT, {
        error: 'Error fetching market health',
    })
}

export async function get_sell_order_supply(location_id: number) {
    const params = new URLSearchParams()
    params.set('location_id', String(location_id))

    const ENDPOINT = `${API_ENDPOINT}/sell-order-supply?${params.toString()}`

    return await api_request<LiveSellOrderSupply>(ENDPOINT, {
        error: 'Error fetching sell-order supply',
    })
}

export async function get_inferred_sales_monthly_types(
    location_id: number,
    year: number,
    month: number,
    options: {
        page?: number
        sort?: string
        sold_class?: string
        q?: string
        access_token?: string | false
    } = {},
): Promise<InferredSalesMonthlyVolumePage> {
    const params = new URLSearchParams()
    params.set('location_id', String(location_id))
    params.set('year', String(year))
    params.set('month', String(month))
    if (options.page != null) params.set('page', String(options.page))
    if (options.sort) params.set('sort', options.sort)
    if (options.sold_class) params.set('sold_class', options.sold_class)
    if (options.q) params.set('q', options.q)

    const ENDPOINT = `${API_ENDPOINT}/inferred-sales/monthly/types?${params.toString()}`

    return await api_request<InferredSalesMonthlyVolumePage>(ENDPOINT, {
        token: options.access_token,
        error: 'Error fetching monthly volume page',
    })
}

export async function get_market_character_statistics() {
    const ENDPOINT = `${API_ENDPOINT}/character-statistics`

    return await api_request<MarketOperatorStatistics[]>(ENDPOINT, {
        error: 'Error fetching market character statistics',
    })
}
