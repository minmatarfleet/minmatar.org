import type {
    Contract,
    ContractMetrics,
    InferredSalesVolume,
    MarketOperatorStatistics,
    OpsMonitor,
    OpsMonitorHistoryPoint,
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

export async function get_ops_monitor(location_id?: number) {
    const headers = {
        'Content-Type': 'application/json',
    }

    let ENDPOINT = `${API_ENDPOINT}/ops-monitor`
    if (location_id !== undefined)
        ENDPOINT += `?location_id=${location_id}`

    try {
        const response = await fetch(ENDPOINT, { headers })
        if (!response.ok) {
            throw new Error(get_error_message(response.status, `GET ${ENDPOINT}`), {
                cause: response.status,
            })
        }
        return await response.json() as OpsMonitor
    } catch (error) {
        throw new Error(`Error fetching ops monitor: ${error.message}`, { cause: error.cause })
    }
}

export async function get_ops_monitor_history(
    location_id?: number,
    options: { days?: number; limit?: number } = { days: 30 },
) {
    const headers = {
        'Content-Type': 'application/json',
    }

    const params = new URLSearchParams()
    if (location_id !== undefined)
        params.set('location_id', String(location_id))
    if (options.days != null)
        params.set('days', String(options.days))
    else if (options.limit != null)
        params.set('limit', String(options.limit))

    const ENDPOINT = `${API_ENDPOINT}/ops-monitor/history?${params.toString()}`

    try {
        const response = await fetch(ENDPOINT, { headers })
        if (!response.ok) {
            throw new Error(get_error_message(response.status, `GET ${ENDPOINT}`), {
                cause: response.status,
            })
        }
        return await response.json() as OpsMonitorHistoryPoint[]
    } catch (error) {
        throw new Error(`Error fetching ops monitor history: ${error.message}`, {
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
