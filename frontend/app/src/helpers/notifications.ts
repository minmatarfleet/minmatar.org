import { useTranslations, useTranslatedPath } from '@i18n/utils';

const t = useTranslations('en')
const translatePath = useTranslatedPath('en')

import { strip_markdown } from '@helpers/string'

import { get_vapid_public_key, get_vapid_private_key, get_vapid_contact } from '@helpers/env'
import { get_player_icon } from '@helpers/eve_image_server';
import { fetch_fleet_by_id, fetch_fleet_users } from '@helpers/fetching/fleets'

import { get_all_subscriptions, remove_subscription } from '@helpers/api.minmatar.org/notifications'
import type { NotificationSubscriptionsFull } from '@dtypes/api.minmatar.org'
import { unique } from '@helpers/array'

import webpush from 'web-push'

const VAPID_CONTACT = get_vapid_contact()
const VAPID_PUBLIC_KEY = get_vapid_public_key()
const VAPID_PRIVATE_KEY = get_vapid_private_key()
const WEBPUSH_ENABLED = VAPID_CONTACT && VAPID_PUBLIC_KEY && VAPID_PRIVATE_KEY

if (WEBPUSH_ENABLED) {
    webpush.setVapidDetails(
        VAPID_CONTACT,
        VAPID_PUBLIC_KEY,
        VAPID_PRIVATE_KEY
    )
}

export async function send_active_fleet_notification(auth_token:string, fleet_id:number) {
    let subscriptions:NotificationSubscriptionsFull[] = []

    try {
        subscriptions = await get_all_subscriptions(auth_token)
    } catch (error) {
        return
    }

    const users = unique(subscriptions, 'user_id')

    const fleet_users = await fetch_fleet_users(fleet_id) ?? []

    const recipients = users.filter((user_id) => fleet_users.includes(user_id))

    const fleet = await fetch_fleet_by_id(auth_token as string, fleet_id)

    const payload = JSON.stringify({
        title: t('push_up_notification_title'),
        body: await strip_markdown(fleet.description),
        icon: get_player_icon(fleet.fleet_commander_id),
        url: translatePath(`/fleets/upcoming/${fleet_id}`),
    });

    subscriptions.map((subscription) => {
        if (recipients.includes(subscription.user_id))
            send_notification(auth_token, JSON.parse(subscription.subscription), payload, subscription.id)
    })
}

const send_notification = (auth_token: string, subscription:any, payload:string, subscription_id:number) => {
    if (!WEBPUSH_ENABLED) return

    webpush.sendNotification(subscription, payload)
        .then(response => {
            console.log('Push notification sent successfully:', response);
        })
        .catch(async error => {
            try {
                if (error.statusCode === 410)
                    await remove_subscription(auth_token, subscription_id)
            } catch (error) {
                console.log(error.message)
            }

            console.error('Error sending push notification:', error);
        });
}