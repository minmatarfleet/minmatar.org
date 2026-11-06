import type { BuybackManageItem, BuybackManageSettings, BuybackSettingsPatch } from '@dtypes/api.minmatar.org'
import { api_request } from '@helpers/api.minmatar.org/client'

const API_ENDPOINT = `${import.meta.env.API_URL}/api/buyback/manage`

/** Rates, location and accepted items, or null when the user may not edit them. */
export async function get_buyback_manage_settings(access_token: string) {
    return await api_request<BuybackManageSettings>(`${API_ENDPOINT}/settings`, {
        token: access_token,
        allow: [403],
    })
}

export async function patch_buyback_settings(access_token: string, payload: BuybackSettingsPatch) {
    return await api_request<BuybackManageSettings>(`${API_ENDPOINT}/settings`, {
        method: 'PATCH',
        token: access_token,
        body: payload,
    })
}

export async function add_buyback_item(access_token: string, type_id: number, category: string) {
    return await api_request<BuybackManageItem>(`${API_ENDPOINT}/items`, {
        method: 'POST',
        token: access_token,
        body: { type_id, category },
    })
}

export async function patch_buyback_item(
    access_token: string,
    type_id: number,
    payload: { active?: boolean, category?: string },
) {
    return await api_request<BuybackManageItem>(`${API_ENDPOINT}/items/${type_id}`, {
        method: 'PATCH',
        token: access_token,
        body: payload,
    })
}

export async function delete_buyback_item(access_token: string, type_id: number) {
    return await api_request(`${API_ENDPOINT}/items/${type_id}`, { method: 'DELETE', token: access_token })
}

export async function search_buyback_types(access_token: string, query: string) {
    return await api_request<{ type_id: number, name: string }[]>(
        `${API_ENDPOINT}/types?q=${encodeURIComponent(query)}`,
        { token: access_token, allow: [403] },
    )
}
