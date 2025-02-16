import { i18n } from '@helpers/i18n'
import type { User } from '@dtypes/jwt'
import * as jose from 'jose'
import { is_prod_mode } from '@helpers/env'
import { HTTP_404_Not_Found, HTTP_403_Forbidden, HTTP_200_Success, HTTP_500_Server_Error } from '@helpers/http_responses'
import { create_subscription, remove_subscription } from '@helpers/api.minmatar.org/notifications'

export async function POST({ request, cookies, redirect }) {
    if (request.headers.get("Content-Type") !== "application/json")
        return HTTP_404_Not_Found()

    const { t } = i18n(new URL(request.url))

    const subscription = await request.json()

    const auth_token = cookies.has('auth_token') ? cookies.get('auth_token').value : false
    const user:User | false = auth_token ? jose.decodeJwt(auth_token) as User : false

    if (!auth_token || !user) {
        return HTTP_403_Forbidden()
    }

    let subscription_id
    try {
        const new_subscription = await create_subscription(auth_token, user.user_id, JSON.stringify(subscription))
        subscription_id = new_subscription.id
    } catch (error) {
        console.log(is_prod_mode() ? t('create_subscription_error') : error.message)
    }

    if (!subscription_id)
        return HTTP_404_Not_Found()

    cookies.set('subscription_id', subscription_id, { path: '/' })
    
    return HTTP_200_Success(JSON.stringify({
        subscription_id: subscription_id
    }))
}

export async function DELETE({ request, cookies }) {
    const { t } = i18n(new URL(request.url))
    
    const auth_token = cookies.has('auth_token') ? cookies.get('auth_token').value : false
    const user:User | false = auth_token ? jose.decodeJwt(auth_token) as User : false
    
    if (!auth_token || !user) {
        return HTTP_403_Forbidden()
    }

    const subscription_id = cookies.has('subscription_id') ? cookies.get('subscription_id').value : null

    if (subscription_id) {
        try {
            await remove_subscription(auth_token, subscription_id)
            cookies.delete('subscription_id', { path: '/' })
            return HTTP_200_Success()
        } catch (error) {
            console.log(error)

            return HTTP_500_Server_Error(JSON.stringify({
                error: is_prod_mode() ? t('delete_subscription_error') : error.message
            }))
        }
    }

    return HTTP_404_Not_Found()
}