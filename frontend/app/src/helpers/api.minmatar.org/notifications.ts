import { get_shared_secret } from '@helpers/env'
import type { NotificationSubscription, NotificationSubscriptionsFull } from '@dtypes/api.minmatar.org'
import { api_request, api_response } from '@helpers/api.minmatar.org/client'

const API_ENDPOINT = `${import.meta.env.API_URL}/api/subscriptions`

export async function get_user_subscriptions(access_token:string, user_id:number) {
    return await api_request<NotificationSubscription[]>(`${API_ENDPOINT}?user_id=${user_id}`, {
        method: 'GET',
        token: access_token,
        error: 'Error fetching user notifications',
    })
}

export async function create_subscription(access_token:string, user_id:number, subscription:string) {
    return await api_request<NotificationSubscription>(`${API_ENDPOINT}/`, {
        method: 'POST',
        token: access_token,
        body: {
            user_id: user_id,
            subscription: subscription,
        },
        error: 'Error creating subscription',
    })
}

/** Signed-out visitors pass false: the shared secret authorises the removal. */
export async function remove_subscription(access_token:string | false, subscription_id:number) {
    await api_response(`${API_ENDPOINT}/${subscription_id}?code=${get_shared_secret()}`, {
        method: 'DELETE',
        token: access_token,
        error: 'Error deleting subscription',
    })

    return subscription_id
}

export async function get_all_subscriptions(access_token:string) {
    return await api_request<NotificationSubscriptionsFull[]>(API_ENDPOINT, {
        method: 'GET',
        token: access_token,
        error: 'Error fetching user notifications',
    })
}