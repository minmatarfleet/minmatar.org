import type {
    LoyaltyAccountCreate,
    LoyaltyAccountPatch,
    LoyaltyContactCreate,
    LoyaltyContactPatch,
    LoyaltyCurrencyCreate,
    LoyaltyCurrencyPatch,
    LoyaltySettingsAccount,
    LoyaltySettingsContact,
    LoyaltySettingsCurrency,
} from '@dtypes/api.minmatar.org'
import { api_request } from '@helpers/api.minmatar.org/client'
import type { LoyaltyPriceChange } from '@helpers/market_settings'

const API_ENDPOINT = `${import.meta.env.API_URL}/api/industry/loyalty/settings`

/** Every LP corp with its accounts and contacts, or null when the user may not edit them. */
export async function get_loyalty_settings(access_token: string) {
    return await api_request<LoyaltySettingsCurrency[]>(API_ENDPOINT, { token: access_token, allow: [403] })
}

export async function add_loyalty_currency(access_token: string, payload: LoyaltyCurrencyCreate) {
    return await api_request<LoyaltySettingsCurrency>(`${API_ENDPOINT}/currencies`, {
        method: 'POST',
        token: access_token,
        body: payload,
    })
}

export async function patch_loyalty_currency(access_token: string, id: number, payload: LoyaltyCurrencyPatch) {
    return await api_request<LoyaltySettingsCurrency>(`${API_ENDPOINT}/currencies/${id}`, {
        method: 'PATCH',
        token: access_token,
        body: payload,
    })
}

export async function add_loyalty_account(access_token: string, payload: LoyaltyAccountCreate) {
    return await api_request<LoyaltySettingsAccount>(`${API_ENDPOINT}/accounts`, {
        method: 'POST',
        token: access_token,
        body: payload,
    })
}

export async function patch_loyalty_account(access_token: string, id: number, payload: LoyaltyAccountPatch) {
    return await api_request<LoyaltySettingsAccount>(`${API_ENDPOINT}/accounts/${id}`, {
        method: 'PATCH',
        token: access_token,
        body: payload,
    })
}

export async function add_loyalty_contact(access_token: string, payload: LoyaltyContactCreate) {
    return await api_request<LoyaltySettingsContact>(`${API_ENDPOINT}/contacts`, {
        method: 'POST',
        token: access_token,
        body: payload,
    })
}

export async function patch_loyalty_contact(access_token: string, id: number, payload: LoyaltyContactPatch) {
    return await api_request<LoyaltySettingsContact>(`${API_ENDPOINT}/contacts/${id}`, {
        method: 'PATCH',
        token: access_token,
        body: payload,
    })
}

export async function delete_loyalty_contact(access_token: string, id: number) {
    return await api_request(`${API_ENDPOINT}/contacts/${id}`, { method: 'DELETE', token: access_token })
}

/** The corp's recent ISK/LP changes, newest first. */
export async function get_loyalty_currency_history(access_token: string, id: number) {
    return await api_request<LoyaltyPriceChange[]>(`${API_ENDPOINT}/currencies/${id}/history`, { token: access_token })
}
