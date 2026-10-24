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
import { api_request } from '@helpers/api.minmatar.org/client'

const API_ENDPOINT = `${import.meta.env.API_URL}/api/buyback`

export async function get_buyback_settings() {
    return await api_request<BuybackSettings>(`${API_ENDPOINT}/settings`, {
        error: 'Error fetching buyback settings',
    })
}

export async function get_buyback_stock() {
    return await api_request<BuybackOnHand>(`${API_ENDPOINT}/stock`, {
        error: 'Error fetching buyback stock',
    })
}

export async function get_buyback_stock_stats() {
    return await api_request<BuybackStockStats>(`${API_ENDPOINT}/stock/stats`, {
        error: 'Error fetching buyback stock stats',
    })
}

export async function get_buyback_ledger(params: {
    reason?: string
    limit?: number
    offset?: number
} = {}) {
    const query = new URLSearchParams()
    if (params.reason) query.set('reason', params.reason)
    if (params.limit != null) query.set('limit', String(params.limit))
    if (params.offset != null) query.set('offset', String(params.offset))
    const qs = query.toString()
    const ENDPOINT = `${API_ENDPOINT}/ledger${qs ? `?${qs}` : ''}`

    return await api_request<BuybackLedger>(ENDPOINT, {
        error: 'Error fetching buyback ledger',
    })
}

export async function post_buyback_appraisal(paste: string) {
    return await api_request<BuybackAppraisal>(`${API_ENDPOINT}/appraise`, {
        method: 'POST',
        body: { paste },
        error: 'Error appraising buyback paste',
    })
}

export async function get_buyback_contracts(history: boolean = false) {
    return await api_request<BuybackContract[]>(`${API_ENDPOINT}/contracts${history ? '/history' : ''}`, {
        error: 'Error fetching buyback contracts',
    })
}

export async function get_buyback_contracts_stats() {
    return await api_request<BuybackContractsStats>(`${API_ENDPOINT}/contracts/stats`, {
        error: 'Error fetching buyback contracts stats',
    })
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
    return await api_request<BuybackPurchaseFill>(`${API_ENDPOINT}/stock/fill`, {
        method: 'POST',
        token: options.access_token,
        body: {
            paste,
            source: source ?? null,
            character_id: options.character_id ?? null,
            facility_key: options.facility_key ?? null,
            use_reprocessing_implants: options.use_reprocessing_implants ?? false,
        },
        error: 'Error filling buyback purchase',
    })
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
    return await api_request<BuybackPurchaseOrder>(`${API_ENDPOINT}/stock/orders`, {
        method: 'POST',
        token: access_token,
        body: {
            paste,
            source: source ?? 'stockpile',
            character_id: options.character_id ?? null,
            facility_key: options.facility_key ?? null,
            use_reprocessing_implants: options.use_reprocessing_implants ?? false,
        },
        error: 'Error placing buyback purchase',
    })
}

export async function get_buyback_purchase_orders(
    access_token: string,
    status?: string,
) {
    const query = new URLSearchParams()
    if (status) query.set('status', status)
    const qs = query.toString()
    const ENDPOINT = `${API_ENDPOINT}/stock/orders${qs ? `?${qs}` : ''}`

    return await api_request<BuybackPurchaseOrderList>(ENDPOINT, {
        token: access_token,
        error: 'Error fetching buyback purchases',
    })
}

export async function post_buyback_purchase_order_complete(
    access_token: string,
    order_id: number,
) {
    return await api_request<BuybackPurchaseOrder>(`${API_ENDPOINT}/stock/orders/${order_id}/complete`, {
        method: 'POST',
        token: access_token,
        error: 'Error completing buyback purchase',
    })
}

export async function post_buyback_purchase_order_cancel(
    access_token: string,
    order_id: number,
) {
    return await api_request<BuybackPurchaseOrder>(`${API_ENDPOINT}/stock/orders/${order_id}/cancel`, {
        method: 'POST',
        token: access_token,
        error: 'Error cancelling buyback purchase',
    })
}

export async function get_buyback_purchase_capabilities(access_token: string) {
    return await api_request<BuybackPurchaseCapabilities>(`${API_ENDPOINT}/stock/purchase-capabilities`, {
        token: access_token,
        error: 'Error fetching buyback purchase capabilities',
    })
}
