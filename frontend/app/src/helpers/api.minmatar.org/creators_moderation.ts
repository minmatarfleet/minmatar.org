import type { CreatorModerationAccount, CreatorModerationItem } from '@dtypes/api.minmatar.org'
import { api_request } from '@helpers/api.minmatar.org/client'
import { query_string } from '@helpers/string'

const API_ENDPOINT = `${import.meta.env.API_URL}/api/creators/moderation`

// The API sends the owner's main (character_id, character_name); optional so
// an older backend still renders.
export type CreatorModerationAccountRow = CreatorModerationAccount & {
    character_id?: number | null
    character_name?: string
}
export type CreatorItemView = 'all' | 'shown' | 'featured' | 'hidden'
export type CreatorItemCounts = { shown: number; featured: number; hidden: number }

export const get_moderation_accounts = (token: string) =>
    api_request<CreatorModerationAccountRow[]>(`${API_ENDPOINT}/accounts`, { token })

export const set_moderation_account_status = (token: string, account_id: number, status: string) =>
    api_request<CreatorModerationAccountRow>(`${API_ENDPOINT}/accounts/${account_id}/status`, {
        method: 'PUT',
        token,
        body: { status },
    })

export const get_moderation_items = (
    token: string,
    account_id: number,
    filters: { view?: CreatorItemView; q?: string; offset?: number; limit?: number } = {},
) => {
    const query = query_string({
        view: filters.view ?? 'all',
        q: filters.q ?? '',
        offset: String(filters.offset ?? 0),
        limit: String(filters.limit ?? 100),
    })
    return api_request<CreatorModerationItem[]>(`${API_ENDPOINT}/accounts/${account_id}/items?${query}`, { token })
}

export const get_moderation_item_counts = (token: string, account_id: number, q = '') =>
    api_request<CreatorItemCounts>(
        `${API_ENDPOINT}/accounts/${account_id}/item-counts?${query_string({ q })}`,
        { token },
    )

export const update_moderation_item = (
    token: string,
    item_id: number,
    body: { hidden?: boolean; featured?: boolean },
) => api_request<CreatorModerationItem>(`${API_ENDPOINT}/items/${item_id}`, { method: 'PUT', token, body })
