import { i18n } from '@helpers/i18n'
import { prod_error_messages } from '@helpers/env'
import type { Character } from '@dtypes/api.minmatar.org'
import { get_primary_characters } from '@helpers/api.minmatar.org/characters'
import { remove_subscription } from '@helpers/api.minmatar.org/notifications'

const ONE_DAY_IN_MS = 24*60*60*1000

export const onRequest = async ({ locals, cookies, request }, next) => {
    const { t, translatePath } = i18n(new URL(request.url))

    locals.clientIP =
        request.headers.get("x-forwarded-for") ||
        request.headers.get("cf-connecting-ip") ||
        request.headers.get("remote-addr") ||
        ''

    const auth_token = cookies.has('auth_token') ? cookies.get('auth_token').value : false

    const url = new URL(request.url)

    if (url.pathname == translatePath('/redirects/add_primary_character'))
        return next()

    if (cookies.has('auth_token') && !cookies.has('primary_pilot')) {
        let primary_pilot:Character
        let get_primary_characters_error = false;

        try {
            primary_pilot = await get_primary_characters(auth_token as string);

            if (primary_pilot?.character_id) {
                const in_1_day = new Date(new Date().getTime()+(ONE_DAY_IN_MS))
                cookies.set('primary_pilot', JSON.stringify(primary_pilot), { path: '/', expires: in_1_day })
            }
        } catch (error) {
            get_primary_characters_error = (prod_error_messages() ? t('get_primary_characters_error') : error.message)
            cookies.set('middleware_error', get_primary_characters_error, { path: '/' })
            console.log(get_primary_characters_error)
        }
    }

    if (!cookies.has('auth_token')) {
        const subscription_id = cookies.has('subscription_id') ? parseInt(cookies.get('subscription_id').value) : null
        
        try {
            (subscription_id ?? 0) > 0 ? await remove_subscription(auth_token, subscription_id as number) : null
            cookies.delete('subscription_id', { path: '/' })
        } catch (error) {
            console.log(error.message)
        }
    }

    return next();
};