import type { CreatorModerationAccount, CreatorModerationItem } from '@dtypes/api.minmatar.org'
import { api_request } from '@helpers/api.minmatar.org/client'

const API_ENDPOINT = `${import.meta.env.API_URL}/api/creators/moderation`

export const get_moderation_accounts = (token: string) =>
    api_request<CreatorModerationAccount[]>(`${API_ENDPOINT}/accounts`, { token })

export const set_moderation_account_status = (token: string, account_id: number, status: string) =>
    api_request<CreatorModerationAccount>(`${API_ENDPOINT}/accounts/${account_id}/status`, {
        method: 'PUT',
        token,
        body: { status },
    })

export const get_moderation_items = (token: string, account_id: number) =>
    api_request<CreatorModerationItem[]>(`${API_ENDPOINT}/accounts/${account_id}/items`, { token })

export const update_moderation_item = (
    token: string,
    item_id: number,
    body: { hidden?: boolean; featured?: boolean },
) => api_request<CreatorModerationItem>(`${API_ENDPOINT}/items/${item_id}`, { method: 'PUT', token, body })
