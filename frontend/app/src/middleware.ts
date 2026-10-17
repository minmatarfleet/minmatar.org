import { i18n } from '@helpers/i18n'
import { prod_error_messages } from '@helpers/env'
import { is_auth_init_redirect, is_noindex_path } from '@helpers/seo'
import type { Character } from '@dtypes/api.minmatar.org'
import { get_primary_characters } from '@helpers/api.minmatar.org/characters'
import { remove_subscription } from '@helpers/api.minmatar.org/notifications'
import { status_page_rewrite } from '@helpers/http_responses'
import { get_request_user } from '@helpers/request_user'

const ONE_DAY_IN_MS = 24*60*60*1000

function should_rewrite_login_redirect(request: Request, response: Response): boolean {
    if (request.method !== 'GET') return false
    if (request.headers.get('HX-Request')) return false

    const url = new URL(request.url)
    if (url.pathname.startsWith('/partials/')) return false
    if (response.status < 300 || response.status >= 400) return false

    const location = response.headers.get('location')
    if (!location) return false
    return is_auth_init_redirect(location, url.origin)
}

export const onRequest = async ({ locals, cookies, request, rewrite }, next) => {
    const { t, translatePath } = i18n(new URL(request.url))

    locals.clientIP =
        request.headers.get("x-forwarded-for") ||
        request.headers.get("cf-connecting-ip") ||
        request.headers.get("remote-addr") ||
        ''

    const { auth_token } = get_request_user({ cookies, locals })

    const url = new URL(request.url)

    if (url.pathname == translatePath('/redirects/add_primary_character'))
        return next()

    if (auth_token && !cookies.has('primary_pilot')) {
        let primary_pilot:Character
        let get_primary_characters_error = false;

        try {
            primary_pilot = await get_primary_characters(auth_token);

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

    const response = await next()

    if (should_rewrite_login_redirect(request, response)) {
        cookies.set('redirect_after_auth', url.href, { path: '/' })
        const rewrite_url = `${translatePath('/redirects/auth_init')}?redirect_url=${encodeURIComponent(url.href)}`
        return rewrite(rewrite_url)
    }

    const status_page = status_page_rewrite(request, response)
    if (status_page)
        return rewrite(translatePath(status_page))

    if (is_noindex_path(url.pathname)) {
        response.headers.set('X-Robots-Tag', 'noindex, nofollow')
    }

    return response
};