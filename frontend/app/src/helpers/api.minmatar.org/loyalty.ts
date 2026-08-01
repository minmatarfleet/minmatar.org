import type {
    LoyaltyCurrency,
    LoyaltyLedgerEntry,
    LoyaltyMarketOrder,
    OrderLpStockpile,
} from '@dtypes/api.minmatar.org'
import { get_error_message, query_string } from '@helpers/string'

const API_ENDPOINT = `${import.meta.env.API_URL}/api/industry/loyalty`

export async function get_loyalty_currencies() {
    const ENDPOINT = `${API_ENDPOINT}/currencies`
    console.log(`Requesting: ${ENDPOINT}`)
    const response = await fetch(ENDPOINT, {
        headers: { 'Content-Type': 'application/json' },
    })
    if (!response.ok) {
        throw new Error(get_error_message(response.status, `GET ${ENDPOINT}`), {
            cause: response.status,
        })
    }
    return await response.json() as LoyaltyCurrency[]
}

export async function get_loyalty_stockpiles() {
    const ENDPOINT = `${API_ENDPOINT}/stockpiles`
    console.log(`Requesting: ${ENDPOINT}`)
    const response = await fetch(ENDPOINT, {
        headers: { 'Content-Type': 'application/json' },
    })
    if (!response.ok) {
        throw new Error(get_error_message(response.status, `GET ${ENDPOINT}`), {
            cause: response.status,
        })
    }
    return await response.json() as OrderLpStockpile[]
}

export async function get_loyalty_ledger(params?: {
    loyalty_point_id?: number
    account_id?: number
    limit?: number
}) {
    const query: Record<string, string> = {}
    if (params?.loyalty_point_id != null)
        query.loyalty_point_id = String(params.loyalty_point_id)
    if (params?.account_id != null)
        query.account_id = String(params.account_id)
    if (params?.limit != null)
        query.limit = String(params.limit)
    const qs = query_string(query)
    const ENDPOINT = `${API_ENDPOINT}/ledger${qs ? `?${qs}` : ''}`
    console.log(`Requesting: ${ENDPOINT}`)
    const response = await fetch(ENDPOINT, {
        headers: { 'Content-Type': 'application/json' },
    })
    if (!response.ok) {
        throw new Error(get_error_message(response.status, `GET ${ENDPOINT}`), {
            cause: response.status,
        })
    }
    return await response.json() as LoyaltyLedgerEntry[]
}

export async function get_loyalty_orders(params?: {
    side?: string
    loyalty_point_id?: number
    status?: string
}) {
    const query: Record<string, string> = {}
    if (params?.side) query.side = params.side
    if (params?.loyalty_point_id != null)
        query.loyalty_point_id = String(params.loyalty_point_id)
    if (params?.status) query.status = params.status
    const qs = query_string(query)
    const ENDPOINT = `${API_ENDPOINT}/orders${qs ? `?${qs}` : ''}`
    console.log(`Requesting: ${ENDPOINT}`)
    const response = await fetch(ENDPOINT, {
        headers: { 'Content-Type': 'application/json' },
    })
    if (!response.ok) {
        throw new Error(get_error_message(response.status, `GET ${ENDPOINT}`), {
            cause: response.status,
        })
    }
    return await response.json() as LoyaltyMarketOrder[]
}
