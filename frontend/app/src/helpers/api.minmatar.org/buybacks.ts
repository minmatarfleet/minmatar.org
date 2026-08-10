import type {
    BuybackAppraisal,
    BuybackContract,
    BuybackContractsStats,
    BuybackLedger,
    BuybackOnHand,
    BuybackSettings,
    BuybackStockStats,
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

export async function get_buyback_stock() {
    const headers = {
        'Content-Type': 'application/json',
    }

    const ENDPOINT = `${API_ENDPOINT}/stock`

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

        return await response.json() as BuybackOnHand;
    } catch (error) {
        throw new Error(`Error fetching buyback stock: ${error.message}`, { cause: error.cause });
    }
}

export async function get_buyback_stock_stats() {
    const headers = {
        'Content-Type': 'application/json',
    }

    const ENDPOINT = `${API_ENDPOINT}/stock/stats`

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

        return await response.json() as BuybackStockStats;
    } catch (error) {
        throw new Error(`Error fetching buyback stock stats: ${error.message}`, { cause: error.cause });
    }
}

export async function get_buyback_ledger(params: {
    reason?: string
    limit?: number
    offset?: number
} = {}) {
    const headers = {
        'Content-Type': 'application/json',
    }

    const query = new URLSearchParams()
    if (params.reason) query.set('reason', params.reason)
    if (params.limit != null) query.set('limit', String(params.limit))
    if (params.offset != null) query.set('offset', String(params.offset))
    const qs = query.toString()
    const ENDPOINT = `${API_ENDPOINT}/ledger${qs ? `?${qs}` : ''}`

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

        return await response.json() as BuybackLedger;
    } catch (error) {
        throw new Error(`Error fetching buyback ledger: ${error.message}`, { cause: error.cause });
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
