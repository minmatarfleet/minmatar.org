import { get_error_message, parse_response_error } from '@helpers/string'

const API_ENDPOINT = `${import.meta.env.API_URL}/api/market`

export interface FittingBuySwap {
    preferred_type_id: number
    substitute_type_id: number
    notes?: string
}

export interface FittingBuyLine {
    id: number
    fitting_id: number
    fitting_name: string
    ship_id: number
    quantity: number
    swaps: FittingBuySwap[]
    max_completable: number | null
    sort_order: number
    eft: string
    has_swaps: boolean
}

export interface FittingBuyAlternate {
    type_id: number
    type_name: string
    jita_sell_volume: number | null
    jita_order_count: number | null
    jita_sell_min: string | null
    cpu?: number | null
    pg?: number | null
}

export interface FittingBuyAllocation {
    type_id: number
    type_name: string
    qty: number
}

export interface FittingBuyItem {
    type_id: number
    type_name: string
    needed_qty: number
    stock_qty: number
    buy_qty: number
    jita_sell_volume: number | null
    jita_order_count: number | null
    jita_sell_min: string | null
    unit_price: string | null
    shortfall: number | null
    is_short: boolean
    cpu?: number | null
    pg?: number | null
    can_allocate?: boolean
    allocate_buy_qty?: number | null
    allocated_from_type_id?: number | null
    alternates: FittingBuyAlternate[]
    allocations: FittingBuyAllocation[]
}

export interface FittingBuySubstitution {
    fitting_id: number
    preferred_type_id: number
    preferred_name: string
    substitute_type_id: number
    substitute_name: string
    notes: string
}

export interface FittingBuyJitaCheck {
    id: number
    status: string
    done_count: number
    total_count: number
    force_refresh: boolean
    error: string
    finished_at: string | null
}

export interface FittingBuyOrderListShip {
    fitting_id: number
    fitting_name: string
    ship_id: number
    quantity: number
}

export interface FittingBuyOrderListItem {
    id: number
    status: string
    owner_id: number
    owner_username: string
    line_count: number
    ships: FittingBuyOrderListShip[]
    include_hull: boolean
    jita_checked_at: string | null
    created_at: string
    updated_at: string
    is_owner: boolean
}

export interface FittingBuyOrderDetail {
    id: number
    status: string
    notes: string
    owner_id: number
    owner_username: string
    stock_paste: string
    include_hull: boolean
    jita_checked_at: string | null
    created_at: string
    updated_at: string
    is_owner: boolean
    lines: FittingBuyLine[]
    items: FittingBuyItem[]
    multibuy: string
    fits_eft: string
    unresolved_stock_names: string[]
    substitutions: FittingBuySubstitution[]
    active_jita_check: FittingBuyJitaCheck | null
}

function auth_headers(access_token: string) {
    return {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${access_token}`,
    }
}

async function parse_json_or_throw(response: Response, method: string, endpoint: string) {
    if (!response.ok) {
        const message = await parse_response_error(response, `${method} ${endpoint}`)
        throw new Error(
            typeof message === 'string' && message
                ? message
                : get_error_message(response.status, `${method} ${endpoint}`),
            { cause: response.status },
        )
    }
    if (response.status === 204)
        return null
    return response.json()
}

export async function list_fitting_buy_orders(
    access_token: string,
    options: { status?: string; mine?: boolean } = {},
) {
    const params = new URLSearchParams()
    if (options.status)
        params.set('status', options.status)
    if (options.mine)
        params.set('mine', 'true')
    const qs = params.toString()
    const endpoint = `${API_ENDPOINT}/fitting-buy-orders${qs ? `?${qs}` : ''}`
    const response = await fetch(endpoint, { headers: auth_headers(access_token) })
    return await parse_json_or_throw(response, 'GET', endpoint) as FittingBuyOrderListItem[]
}

export async function get_fitting_buy_order(access_token: string, order_id: number) {
    const endpoint = `${API_ENDPOINT}/fitting-buy-orders/${order_id}`
    const response = await fetch(endpoint, { headers: auth_headers(access_token) })
    return await parse_json_or_throw(response, 'GET', endpoint) as FittingBuyOrderDetail
}

export async function create_fitting_buy_order(
    access_token: string,
    payload: {
        notes?: string
        include_hull?: boolean
        lines: { fitting_id: number; quantity: number }[]
    },
) {
    const endpoint = `${API_ENDPOINT}/fitting-buy-orders`
    const response = await fetch(endpoint, {
        method: 'POST',
        headers: auth_headers(access_token),
        body: JSON.stringify(payload),
    })
    return await parse_json_or_throw(response, 'POST', endpoint) as FittingBuyOrderDetail
}

export async function patch_fitting_buy_order(
    access_token: string,
    order_id: number,
    payload: {
        notes?: string
        status?: string
        stock_paste?: string
        include_hull?: boolean
    },
) {
    const endpoint = `${API_ENDPOINT}/fitting-buy-orders/${order_id}`
    const response = await fetch(endpoint, {
        method: 'PATCH',
        headers: auth_headers(access_token),
        body: JSON.stringify(payload),
    })
    return await parse_json_or_throw(response, 'PATCH', endpoint) as FittingBuyOrderDetail
}

export async function upsert_fitting_buy_line(
    access_token: string,
    order_id: number,
    payload: { fitting_id: number; quantity: number },
) {
    const endpoint = `${API_ENDPOINT}/fitting-buy-orders/${order_id}/lines`
    const response = await fetch(endpoint, {
        method: 'POST',
        headers: auth_headers(access_token),
        body: JSON.stringify(payload),
    })
    return await parse_json_or_throw(response, 'POST', endpoint) as FittingBuyOrderDetail
}

export async function delete_fitting_buy_line(
    access_token: string,
    order_id: number,
    line_id: number,
) {
    const endpoint = `${API_ENDPOINT}/fitting-buy-orders/${order_id}/lines/${line_id}`
    const response = await fetch(endpoint, {
        method: 'DELETE',
        headers: auth_headers(access_token),
    })
    return await parse_json_or_throw(response, 'DELETE', endpoint) as FittingBuyOrderDetail
}

export async function apply_fitting_buy_swap(
    access_token: string,
    order_id: number,
    line_id: number,
    payload: { preferred_type_id: number; substitute_type_id: number; notes?: string },
) {
    const endpoint = `${API_ENDPOINT}/fitting-buy-orders/${order_id}/lines/${line_id}/swaps`
    const response = await fetch(endpoint, {
        method: 'POST',
        headers: auth_headers(access_token),
        body: JSON.stringify(payload),
    })
    return await parse_json_or_throw(response, 'POST', endpoint) as FittingBuyOrderDetail
}

export async function apply_fitting_buy_order_swap(
    access_token: string,
    order_id: number,
    payload: { preferred_type_id: number; substitute_type_id: number; notes?: string },
) {
    const endpoint = `${API_ENDPOINT}/fitting-buy-orders/${order_id}/swaps`
    const response = await fetch(endpoint, {
        method: 'POST',
        headers: auth_headers(access_token),
        body: JSON.stringify(payload),
    })
    return await parse_json_or_throw(response, 'POST', endpoint) as FittingBuyOrderDetail
}

export async function put_fitting_buy_allocations(
    access_token: string,
    order_id: number,
    payload: {
        preferred_type_id: number
        entries: { type_id: number; qty: number }[]
    },
) {
    const endpoint = `${API_ENDPOINT}/fitting-buy-orders/${order_id}/allocations`
    const response = await fetch(endpoint, {
        method: 'PUT',
        headers: auth_headers(access_token),
        body: JSON.stringify(payload),
    })
    return await parse_json_or_throw(response, 'PUT', endpoint) as FittingBuyOrderDetail
}

export async function start_fitting_buy_jita_check(
    access_token: string,
    order_id: number,
    payload: { force_refresh?: boolean; type_ids?: number[] } = {},
) {
    const endpoint = `${API_ENDPOINT}/fitting-buy-orders/${order_id}/check-jita`
    const response = await fetch(endpoint, {
        method: 'POST',
        headers: auth_headers(access_token),
        body: JSON.stringify(payload),
    })
    return await parse_json_or_throw(response, 'POST', endpoint) as FittingBuyJitaCheck
}

export async function poll_fitting_buy_jita_check(
    access_token: string,
    order_id: number,
    check_id: number,
) {
    const endpoint = `${API_ENDPOINT}/fitting-buy-orders/${order_id}/check-jita/${check_id}`
    const response = await fetch(endpoint, { headers: auth_headers(access_token) })
    return await parse_json_or_throw(response, 'GET', endpoint) as {
        check: FittingBuyJitaCheck
        order: FittingBuyOrderDetail | null
    }
}

export async function paste_fitting_buy_landed_prices(
    access_token: string,
    order_id: number,
    paste: string,
) {
    const endpoint = `${API_ENDPOINT}/fitting-buy-orders/${order_id}/landed-prices`
    const response = await fetch(endpoint, {
        method: 'POST',
        headers: auth_headers(access_token),
        body: JSON.stringify({ paste }),
    })
    return await parse_json_or_throw(response, 'POST', endpoint) as {
        updated: number
        unresolved: string[]
        order: FittingBuyOrderDetail
    }
}
