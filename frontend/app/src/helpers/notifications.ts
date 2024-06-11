
import { useTranslations, useTranslatedPath } from '@i18n/utils';

const t = useTranslations('en')
const translatePath = useTranslatedPath('en')

import { get_player_icon } from '@helpers/eve_image_server';
import { fetch_fleet_by_id } from '@helpers/fetching/fleets'

import { get_all_subscriptions, remove_subscription } from '@helpers/db/notification_subscriptions'
import { unique } from '@helpers/array'

import webpush from 'web-push'

const vapidKeys = {
    publicKey: 'BFucqTUQisrCDaeQpaxyDsH4y2i7CGjn_c3k5akdtxQnAwkevP_ufaJqx8hACWHwR6hJIFg1qKbRVKAvH8cQdnM',
    privateKey: 'a3gSYp-WROTUMTlP-6jDCIU8OxWhNpZ8_5uEWd8q8yY'
}

webpush.setVapidDetails(
    'mailto:beautifulmim.eve@gmail.com',
    vapidKeys.publicKey,
    vapidKeys.privateKey
)

export async function send_active_fleet_notification(auth_token:string, fleet_id:number) {
    const subscriptions = await get_all_subscriptions()
    const users = unique(subscriptions, 'user_id')

    const recipients = users // Get notification recipeints endpoint

    const fleet = await fetch_fleet_by_id(auth_token as string, fleet_id)

    const payload = JSON.stringify({
        title: t('push_up_notification_title'),
        body: fleet.description,
        icon: get_player_icon(fleet.fleet_commander_id),
        url: translatePath(`/fleets/upcoming/${fleet_id}`),
    });

    subscriptions.map((subscription) => {
        if (recipients.includes(subscription.user_id))
            send_notification(subscription.subscription, payload, subscription.id)
    })
}

const send_notification = (subscription:any, payload:string, subscription_id:number) => {
    webpush.sendNotification(subscription, payload)
        .then(response => {
            console.log('Push notification sent successfully:', response);
        })
        .catch(async error => {
            if (error.statusCode === 410)
                await remove_subscription(subscription_id)

            console.error('Error sending push notification:', error);
        });
}