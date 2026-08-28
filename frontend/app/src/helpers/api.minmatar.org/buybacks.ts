import type {
    BuybackAppraisal,
    BuybackContract,
    BuybackContractsStats,
    BuybackLedger,
    BuybackOnHand,
    BuybackPurchaseCapabilities,
    BuybackPurchaseFill,
    BuybackPurchaseOrder,
    BuybackPurchaseOrderList,
    BuybackSettings,
    BuybackStockStats,
} from '@dtypes/api.minmatar.org'
import { get_error_message, parse_response_error } from '@helpers/string'

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

export async function post_buyback_stock_fill(
    paste: string,
    source?: string,
    options: {
        access_token?: string | false | null
        character_id?: number | null
        facility_key?: string | null
        use_reprocessing_implants?: boolean
    } = {},
) {
    const headers: Record<string, string> = {
        'Content-Type': 'application/json',
    }
    if (options.access_token)
        headers.Authorization = `Bearer ${options.access_token}`

    const ENDPOINT = `${API_ENDPOINT}/stock/fill`

    console.log(`Requesting POST: ${ENDPOINT}`)

    try {
        const response = await fetch(ENDPOINT, {
            headers: headers,
            method: 'POST',
            body: JSON.stringify({
                paste,
                source: source ?? null,
                character_id: options.character_id ?? null,
                facility_key: options.facility_key ?? null,
                use_reprocessing_implants: options.use_reprocessing_implants ?? false,
            }),
        })

        if (!response.ok) {
            throw new Error(await parse_response_error(
                response,
                `POST ${ENDPOINT}`
            ), {
                cause: response.status
            });
        }

        return await response.json() as BuybackPurchaseFill;
    } catch (error) {
        throw new Error(`Error filling buyback purchase: ${error.message}`, { cause: error.cause });
    }
}

export async function post_buyback_purchase_order(
    access_token: string,
    paste: string,
    source?: string,
    options: {
        character_id?: number | null
        facility_key?: string | null
        use_reprocessing_implants?: boolean
    } = {},
) {
    const headers = {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${access_token}`,
    }

    const ENDPOINT = `${API_ENDPOINT}/stock/orders`

    console.log(`Requesting POST: ${ENDPOINT}`)

    try {
        const response = await fetch(ENDPOINT, {
            headers: headers,
            method: 'POST',
            body: JSON.stringify({
                paste,
                source: source ?? 'stockpile',
                character_id: options.character_id ?? null,
                facility_key: options.facility_key ?? null,
                use_reprocessing_implants: options.use_reprocessing_implants ?? false,
            }),
        })

        if (!response.ok) {
            throw new Error(await parse_response_error(
                response,
                `POST ${ENDPOINT}`
            ), {
                cause: response.status
            });
        }

        return await response.json() as BuybackPurchaseOrder;
    } catch (error) {
        throw new Error(`Error placing buyback purchase: ${error.message}`, { cause: error.cause });
    }
}

export async function get_buyback_purchase_orders(
    access_token: string,
    status?: string,
) {
    const headers = {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${access_token}`,
    }

    const query = new URLSearchParams()
    if (status) query.set('status', status)
    const qs = query.toString()
    const ENDPOINT = `${API_ENDPOINT}/stock/orders${qs ? `?${qs}` : ''}`

    console.log(`Requesting: ${ENDPOINT}`)

    try {
        const response = await fetch(ENDPOINT, {
            headers: headers,
        })

        if (!response.ok) {
            throw new Error(await parse_response_error(
                response,
                `GET ${ENDPOINT}`
            ), {
                cause: response.status
            });
        }

        return await response.json() as BuybackPurchaseOrderList;
    } catch (error) {
        throw new Error(`Error fetching buyback purchases: ${error.message}`, { cause: error.cause });
    }
}

export async function post_buyback_purchase_order_complete(
    access_token: string,
    order_id: number,
) {
    const headers = {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${access_token}`,
    }

    const ENDPOINT = `${API_ENDPOINT}/stock/orders/${order_id}/complete`

    console.log(`Requesting POST: ${ENDPOINT}`)

    try {
        const response = await fetch(ENDPOINT, {
            headers: headers,
            method: 'POST',
        })

        if (!response.ok) {
            throw new Error(await parse_response_error(
                response,
                `POST ${ENDPOINT}`
            ), {
                cause: response.status
            });
        }

        return await response.json() as BuybackPurchaseOrder;
    } catch (error) {
        throw new Error(`Error completing buyback purchase: ${error.message}`, { cause: error.cause });
    }
}

export async function post_buyback_purchase_order_cancel(
    access_token: string,
    order_id: number,
) {
    const headers = {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${access_token}`,
    }

    const ENDPOINT = `${API_ENDPOINT}/stock/orders/${order_id}/cancel`

    console.log(`Requesting POST: ${ENDPOINT}`)

    try {
        const response = await fetch(ENDPOINT, {
            headers: headers,
            method: 'POST',
        })

        if (!response.ok) {
            throw new Error(await parse_response_error(
                response,
                `POST ${ENDPOINT}`
            ), {
                cause: response.status
            });
        }

        return await response.json() as BuybackPurchaseOrder;
    } catch (error) {
        throw new Error(`Error cancelling buyback purchase: ${error.message}`, { cause: error.cause });
    }
}

export async function get_buyback_purchase_capabilities(access_token: string) {
    const headers = {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${access_token}`,
    }

    const ENDPOINT = `${API_ENDPOINT}/stock/purchase-capabilities`

    console.log(`Requesting: ${ENDPOINT}`)

    try {
        const response = await fetch(ENDPOINT, {
            headers: headers,
        })

        if (!response.ok) {
            throw new Error(await parse_response_error(
                response,
                `GET ${ENDPOINT}`
            ), {
                cause: response.status
            });
        }

        return await response.json() as BuybackPurchaseCapabilities;
    } catch (error) {
        throw new Error(`Error fetching buyback purchase capabilities: ${error.message}`, { cause: error.cause });
    }
}
