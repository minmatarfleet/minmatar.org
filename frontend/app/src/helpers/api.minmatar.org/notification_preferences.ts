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

export type PreferenceUpdateItem = {
    notification_type: string
    channel: string
    enabled: boolean
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

export async function update_notification_preferences(
    access_token: string,
    preferences: PreferenceUpdateItem[]
) {
    const headers = {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${access_token}`,
    }
    const ENDPOINT = `${API_ENDPOINT}/preferences`
    const response = await fetch(ENDPOINT, {
        headers,
        method: 'PUT',
        body: JSON.stringify({ preferences }),
    })
    if (!response.ok) {
        throw new Error(
            await parse_response_error(response, `PUT ${ENDPOINT}`),
            { cause: response.status }
        )
    }
    return (await response.json()) as NotificationFeaturePreferences[]
}

export async function subscribe_notification_topic(
    access_token: string,
    type_key: string
) {
    const headers = {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${access_token}`,
    }
    const ENDPOINT = `${API_ENDPOINT}/topics/${encodeURIComponent(type_key)}`
    const response = await fetch(ENDPOINT, { headers, method: 'POST' })
    if (!response.ok) {
        throw new Error(
            await parse_response_error(response, `POST ${ENDPOINT}`),
            { cause: response.status }
        )
    }
    return response.json()
}

export async function unsubscribe_notification_topic(
    access_token: string,
    type_key: string
) {
    const headers = {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${access_token}`,
    }
    const ENDPOINT = `${API_ENDPOINT}/topics/${encodeURIComponent(type_key)}`
    const response = await fetch(ENDPOINT, { headers, method: 'DELETE' })
    if (!response.ok) {
        throw new Error(
            await parse_response_error(response, `DELETE ${ENDPOINT}`),
            { cause: response.status }
        )
    }
}
