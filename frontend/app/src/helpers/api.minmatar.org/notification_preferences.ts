import { api_request } from '@helpers/api.minmatar.org/client'

const API_ENDPOINT = `${import.meta.env.API_URL}/api/notifications`

export type NotificationChannelPreference = {
    channel: string
    enabled: boolean
    allowed: boolean
}

export type NotificationTypePreference = {
    key: string
    feature: string
    label: string
    description: string
    supports_topic_subscription: boolean
    topic_subscribed: boolean
    channels: NotificationChannelPreference[]
}

export type NotificationFeaturePreferences = {
    feature: string
    types: NotificationTypePreference[]
}

export async function get_notification_preferences(access_token: string) {
    return await api_request<NotificationFeaturePreferences[]>(`${API_ENDPOINT}/preferences`, {
        method: 'GET',
        token: access_token,
    })
}