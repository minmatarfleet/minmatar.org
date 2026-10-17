import { parse_response_error } from '@helpers/string'

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
    const headers = {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${access_token}`,
    }
    const ENDPOINT = `${API_ENDPOINT}/preferences`
    const response = await fetch(ENDPOINT, { headers, method: 'GET' })
    if (!response.ok) {
        throw new Error(
            await parse_response_error(response, `GET ${ENDPOINT}`),
            { cause: response.status }
        )
    }
    return (await response.json()) as NotificationFeaturePreferences[]
}
