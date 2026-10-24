import type {
    LoyaltyCurrency,
    LoyaltyMarketOrder,
    LoyaltyMarketOrdersList,
    LoyaltyOffersList,
    LoyaltyOrderStats,
} from '@dtypes/api.minmatar.org'
import { query_string } from '@helpers/string'
import { api_request } from '@helpers/api.minmatar.org/client'

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
    exclude_blueprints?: string
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
    return await api_request<LoyaltyCapabilities>(ENDPOINT, {
        token: access_token,
    })
}

export async function get_loyalty_currencies() {
    const ENDPOINT = `${API_ENDPOINT}/currencies`
    return await api_request<LoyaltyCurrency[]>(ENDPOINT)
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
    if (params?.exclude_blueprints)
        query.exclude_blueprints = params.exclude_blueprints
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
    return await api_request<LoyaltyOffersList>(ENDPOINT)
}

export interface LoyaltyOrdersQuery {
    side?: string
    loyalty_point_id?: number
    /** Comma-separated statuses; the API defaults to active orders. */
    status?: string
    ordering?: 'created_at' | '-created_at' | 'updated_at' | '-updated_at'
    limit?: number
    offset?: number
}

export async function get_loyalty_orders(params?: LoyaltyOrdersQuery) {
    const query: Record<string, string> = {}
    if (params?.side) query.side = params.side
    if (params?.loyalty_point_id != null)
        query.loyalty_point_id = String(params.loyalty_point_id)
    if (params?.status) query.status = params.status
    if (params?.ordering) query.ordering = params.ordering
    if (params?.limit != null) query.limit = String(params.limit)
    if (params?.offset != null) query.offset = String(params.offset)
    const qs = query_string(query)
    const ENDPOINT = `${API_ENDPOINT}/orders${qs ? `?${qs}` : ''}`
    return await api_request<LoyaltyMarketOrdersList>(ENDPOINT)
}

export async function get_loyalty_stats(loyalty_point_id?: number, days?: number) {
    const query: Record<string, string> = {}
    if (loyalty_point_id != null) query.loyalty_point_id = String(loyalty_point_id)
    if (days != null) query.days = String(days)
    const qs = query_string(query)
    const ENDPOINT = `${API_ENDPOINT}/stats${qs ? `?${qs}` : ''}`
    return await api_request<LoyaltyOrderStats>(ENDPOINT)
}

export async function get_loyalty_order(order_id: number) {
    const ENDPOINT = `${API_ENDPOINT}/orders/${order_id}`
    return await api_request<LoyaltyMarketOrder>(ENDPOINT)
}

export interface LoyaltyOrderPatch {
    status?: string
    notes?: string
}

/** Move an order on: the API checks the caller may take this step. */
export async function patch_loyalty_order(
    access_token: string,
    order_id: number,
    body: LoyaltyOrderPatch,
) {
    const ENDPOINT = `${API_ENDPOINT}/orders/${order_id}`
    return await api_request<LoyaltyMarketOrder>(ENDPOINT, {
        method: 'PATCH',
        token: access_token,
        body: body,
    })
}
