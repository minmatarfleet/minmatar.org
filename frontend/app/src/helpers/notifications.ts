
import { useTranslations, useTranslatedPath } from '@i18n/utils';

import { get_error_message } from '@helpers/string'

const t = useTranslations('en')
const translatePath = useTranslatedPath('en')

import { marked } from 'marked';
import * as cheerio from 'cheerio';

import { get_player_icon } from '@helpers/eve_image_server';
import { fetch_fleet_by_id, fetch_fleet_users } from '@helpers/fetching/fleets'

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

    const fleet_users = await fetch_fleet_users(fleet_id)

    const recipients = users.filter((user_id) => fleet_users.includes(user_id))

    const fleet = await fetch_fleet_by_id(auth_token as string, fleet_id)

    const $ = cheerio.load(await marked.parse(fleet.description))

    const payload = JSON.stringify({
        title: t('push_up_notification_title'),
        body: $('p:first').text(),
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