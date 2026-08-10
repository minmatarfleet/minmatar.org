import type {
    Contract,
    ContractMetrics,
    InferredSalesVolume,
    LiveSellOrderSupply,
    MarketHealth,
    MarketOperatorStatistics,
} from '@dtypes/api.minmatar.org'
import { get_error_message } from '@helpers/string'

const API_ENDPOINT =  `${import.meta.env.API_URL}/api/market`

export async function get_market_contracts(location_id: number) {
    const headers = {
        'Content-Type': 'application/json',
    }

    const ENDPOINT = `${API_ENDPOINT}/contracts?location_id=${location_id}`

    console.log(`Requesting: ${ENDPOINT}`)

    try {
        const response = await fetch(ENDPOINT, {
            headers: headers
        })

        if (!response.ok) {
            throw new Error(get_error_message(
                response.status,
                `GET ${ENDPOINT}`
            ), {
                cause: response.status
            })
        }

        return await response.json() as Contract[];
    } catch (error) {
        throw new Error(`Error fetching contracts: ${error.message}`, { cause: error.cause });
    }
}

export async function get_market_contracts_metrics(location_id: number) {
    const headers = {
        'Content-Type': 'application/json',
    }

    const ENDPOINT = `${API_ENDPOINT}/contracts/metrics?location_id=${location_id}`

    try {
        const response = await fetch(ENDPOINT, { headers })
        if (!response.ok) {
            throw new Error(get_error_message(
                response.status,
                `GET ${ENDPOINT}`
            ), {
                cause: response.status,
            })
        }
        return await response.json() as ContractMetrics[]
    } catch (error) {
        throw new Error(
            `Error fetching contract metrics: ${error.message}`,
            { cause: error.cause },
        )
    }
}

export async function get_market_health(
    location_id: number,
    options: { days?: number } = { days: 30 },
) {
    const headers = {
        'Content-Type': 'application/json',
    }

    const params = new URLSearchParams()
    params.set('location_id', String(location_id))
    if (options.days != null)
        params.set('days', String(options.days))

    const ENDPOINT = `${API_ENDPOINT}/health?${params.toString()}`

    try {
        const response = await fetch(ENDPOINT, { headers })
        if (!response.ok) {
            throw new Error(get_error_message(response.status, `GET ${ENDPOINT}`), {
                cause: response.status,
            })
        }
        return await response.json() as MarketHealth
    } catch (error) {
        throw new Error(`Error fetching market health: ${error.message}`, {
            cause: error.cause,
        })
    }
}

export async function get_sell_order_supply(location_id: number) {
    const headers = {
        'Content-Type': 'application/json',
    }

    const params = new URLSearchParams()
    params.set('location_id', String(location_id))

    const ENDPOINT = `${API_ENDPOINT}/sell-order-supply?${params.toString()}`

    try {
        const response = await fetch(ENDPOINT, { headers })
        if (!response.ok) {
            throw new Error(get_error_message(response.status, `GET ${ENDPOINT}`), {
                cause: response.status,
            })
        }
        return await response.json() as LiveSellOrderSupply
    } catch (error) {
        throw new Error(`Error fetching sell-order supply: ${error.message}`, {
            cause: error.cause,
        })
    }
}

export async function get_inferred_sales_volume(
    location_id: number,
    days = 7,
    type_id?: number,
) {
    const headers = {
        'Content-Type': 'application/json',
    }

    const params = new URLSearchParams()
    params.set('location_id', String(location_id))
    params.set('days', String(days))
    if (type_id !== undefined)
        params.set('type_id', String(type_id))

    const ENDPOINT = `${API_ENDPOINT}/inferred-sales/volume?${params.toString()}`

    try {
        const response = await fetch(ENDPOINT, { headers })
        if (!response.ok) {
            throw new Error(get_error_message(response.status, `GET ${ENDPOINT}`), {
                cause: response.status,
            })
        }
        return await response.json() as InferredSalesVolume
    } catch (error) {
        throw new Error(`Error fetching inferred sales volume: ${error.message}`, {
            cause: error.cause,
        })
    }
}

export async function get_market_character_statistics() {
    const headers = {
        'Content-Type': 'application/json',
    }

    const ENDPOINT = `${API_ENDPOINT}/character-statistics`

    try {
        const response = await fetch(ENDPOINT, { headers })
        if (!response.ok) {
            throw new Error(get_error_message(response.status, `GET ${ENDPOINT}`), {
                cause: response.status,
            })
        }
        return await response.json() as MarketOperatorStatistics[]
    } catch (error) {
        throw new Error(`Error fetching market character statistics: ${error.message}`, {
            cause: error.cause,
        })
    }
}
