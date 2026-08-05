import type {
    LoyaltyCurrency,
    LoyaltyLedgerEntry,
    LoyaltyMarketOrder,
    LoyaltyOffersList,
    OrderLpStockpile,
} from '@dtypes/api.minmatar.org'
import { get_error_message, query_string } from '@helpers/string'

const API_ENDPOINT = `${import.meta.env.API_URL}/api/industry/loyalty`

export interface LoyaltyCapabilities {
    can_manage: boolean
    can_trade: boolean
}

export interface LoyaltyOffersQuery {
    currency?: number
    exclude_tags?: string
    exclude_supply_packages?: string
    exclude_chips?: string
    exclude_skins?: string
    exclude_useless_offers?: string
    exclude_below_set_lp_price?: string
    side?: 'sell' | 'buy' | 'avg_7d'
    q?: string
    ordering?: string
    limit?: number
    offset?: number
}

export async function get_loyalty_capabilities(access_token: string) {
    const ENDPOINT = `${API_ENDPOINT}/capabilities`
    console.log(`Requesting: ${ENDPOINT}`)
    const headers = {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${access_token}`,
    }
    const response = await fetch(ENDPOINT, { headers })
    if (!response.ok) {
        throw new Error(get_error_message(response.status, `GET ${ENDPOINT}`), {
            cause: response.status,
        })
    }
    return await response.json() as LoyaltyCapabilities
}

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

export async function get_loyalty_offers(params?: LoyaltyOffersQuery) {
    const query: Record<string, string> = {}
    if (params?.currency != null)
        query.currency = String(params.currency)
    if (params?.exclude_tags)
        query.exclude_tags = params.exclude_tags
    if (params?.exclude_supply_packages)
        query.exclude_supply_packages = params.exclude_supply_packages
    if (params?.exclude_chips)
        query.exclude_chips = params.exclude_chips
    if (params?.exclude_skins)
        query.exclude_skins = params.exclude_skins
    if (params?.exclude_useless_offers)
        query.exclude_useless_offers = params.exclude_useless_offers
    if (params?.exclude_below_set_lp_price)
        query.exclude_below_set_lp_price = params.exclude_below_set_lp_price
    if (params?.side)
        query.side = params.side
    if (params?.q)
        query.q = params.q
    if (params?.ordering)
        query.ordering = params.ordering
    if (params?.limit != null)
        query.limit = String(params.limit)
    if (params?.offset != null)
        query.offset = String(params.offset)
    const qs = query_string(query)
    const ENDPOINT = `${API_ENDPOINT}/offers${qs ? `?${qs}` : ''}`
    console.log(`Requesting: ${ENDPOINT}`)
    const response = await fetch(ENDPOINT, {
        headers: { 'Content-Type': 'application/json' },
    })
    if (!response.ok) {
        throw new Error(get_error_message(response.status, `GET ${ENDPOINT}`), {
            cause: response.status,
        })
    }
    return await response.json() as LoyaltyOffersList
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
