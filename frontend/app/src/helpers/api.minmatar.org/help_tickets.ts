import type { HelpCategory, HelpCategoryCreate, HelpCategoryPatch, HelpPanel, HelpSettings } from '@dtypes/api.minmatar.org'
import { api_request } from '@helpers/api.minmatar.org/client'

// Help ticket categories and the #help panel channel.
// Every endpoint answers 403 without the help_tickets.manage feature.
const API_ENDPOINT = `${import.meta.env.API_URL}/api/help-tickets/manage`

export async function get_help_settings(access_token: string) {
    return await api_request<HelpSettings>(`${API_ENDPOINT}/settings`, {
        token: access_token,
        error: 'Error fetching help ticket settings',
    })
}

export async function create_help_category(access_token: string, category: HelpCategoryCreate) {
    return await api_request<HelpCategory>(`${API_ENDPOINT}/categories`, {
        method: 'POST',
        token: access_token,
        body: category,
    })
}

export async function update_help_category(access_token: string, category_id: number, changes: HelpCategoryPatch) {
    return await api_request<HelpCategory>(`${API_ENDPOINT}/categories/${category_id}`, {
        method: 'PATCH',
        token: access_token,
        body: changes,
    })
}

export async function order_help_categories(access_token: string, ids: number[]) {
    return await api_request<HelpCategory[]>(`${API_ENDPOINT}/category-order`, {
        method: 'POST',
        token: access_token,
        body: { ids },
    })
}

export async function update_help_panel(access_token: string, channel_id: string) {
    return await api_request<HelpPanel>(`${API_ENDPOINT}/panel`, {
        method: 'PATCH',
        token: access_token,
        body: { channel_id },
    })
}
