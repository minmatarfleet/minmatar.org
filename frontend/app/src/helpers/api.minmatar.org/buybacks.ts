import type {
    BuybackAppraisal,
    BuybackContract,
    BuybackContractsStats,
    BuybackSettings,
} from '@dtypes/api.minmatar.org'
import { get_error_message } from '@helpers/string'

const API_ENDPOINT = `${import.meta.env.API_URL}/api/buyback`

export async function get_buyback_settings() {
    const headers = {
        'Content-Type': 'application/json',
    }

    const ENDPOINT = `${API_ENDPOINT}/settings`

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
            });
        }

        return await response.json() as BuybackSettings;
    } catch (error) {
        throw new Error(`Error fetching buyback settings: ${error.message}`, { cause: error.cause });
    }
}

export async function post_buyback_appraisal(paste: string) {
    const headers = {
        'Content-Type': 'application/json',
    }

    const ENDPOINT = `${API_ENDPOINT}/appraise`

    console.log(`Requesting POST: ${ENDPOINT}`)

    try {
        const response = await fetch(ENDPOINT, {
            headers: headers,
            method: 'POST',
            body: JSON.stringify({ paste }),
        })

        if (!response.ok) {
            throw new Error(get_error_message(
                response.status,
                `POST ${ENDPOINT}`
            ), {
                cause: response.status
            });
        }

        return await response.json() as BuybackAppraisal;
    } catch (error) {
        throw new Error(`Error appraising buyback paste: ${error.message}`, { cause: error.cause });
    }
}

export async function get_buyback_contracts(history: boolean = false) {
    const headers = {
        'Content-Type': 'application/json',
    }

    const ENDPOINT = `${API_ENDPOINT}/contracts${history ? '/history' : ''}`

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
            });
        }

        return await response.json() as BuybackContract[];
    } catch (error) {
        throw new Error(`Error fetching buyback contracts: ${error.message}`, { cause: error.cause });
    }
}

export async function get_buyback_contracts_stats() {
    const headers = {
        'Content-Type': 'application/json',
    }

    const ENDPOINT = `${API_ENDPOINT}/contracts/stats`

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
            });
        }

        return await response.json() as BuybackContractsStats;
    } catch (error) {
        throw new Error(`Error fetching buyback contracts stats: ${error.message}`, { cause: error.cause });
    }
}
