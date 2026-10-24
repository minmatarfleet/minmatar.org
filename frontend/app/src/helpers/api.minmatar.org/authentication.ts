import type { UserProfile } from '@dtypes/api.minmatar.org'
import { api_request, api_status_is } from '@helpers/api.minmatar.org/client'

const API_ENDPOINT =  `${import.meta.env.API_URL}/api/users`

export async function get_user_by_id(user_id:number) {
    return await api_request<UserProfile>(`${API_ENDPOINT}/${user_id}/profile`, {
        error: 'Error fetching user profile',
    })
}

export async function get_users_by_id(user_ids:number[]) {
    return await api_request<UserProfile[]>(`${API_ENDPOINT}/profiles?ids=${user_ids.join(',')}`, {
        error: 'Error fetching user profile',
    })
}

export async function get_user_by_name(user_name:string) {
    return await api_request<UserProfile>(`${API_ENDPOINT}?username=${user_name}`, {
        error: 'Error fetching user profile',
    })
}

export async function delete_account(access_token:string) {
    return await api_status_is(`${API_ENDPOINT}/delete`, {
        method: 'DELETE',
        token: access_token,
        error: 'Error deleting account',
    })
}

export async function sync_user_with_discord(access_token:string, user_id:number) {
    return await api_status_is(`${API_ENDPOINT}/${user_id}/sync`, {
        method: 'POST',
        token: access_token,
        error: 'Error syncing user roles with Discord',
    })
}
