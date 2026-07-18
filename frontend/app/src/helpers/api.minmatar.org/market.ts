import type {
    Contract,
    OpsMonitor,
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

        // console.log(response)

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
