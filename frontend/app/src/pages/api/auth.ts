import { get_request_user } from '@helpers/request_user'
import { i18n } from '@helpers/i18n'
import { is_prod_mode } from '@helpers/env'
import { HTTP_200_Success, HTTP_404_Not_Found, HTTP_403_Forbidden } from '@helpers/http_responses'
import { delete_account } from '@helpers/api.minmatar.org/authentication'

export async function DELETE({ request, params, cookies, locals }) {
    const { t, translatePath } = i18n(new URL(request.url))

    const { auth_token, user } = get_request_user({ cookies, locals })

    if (!auth_token || !user) {
        return HTTP_403_Forbidden()
    }

    let status = false
    try {
        status = await delete_account(auth_token)
    } catch (error) {
        console.log(is_prod_mode() ? t('delete_account_error') : error.message)
    }

    if (!status)
        return HTTP_404_Not_Found()
    
    cookies.delete('auth_token', { path: '/' })
    cookies.delete('avatar', { path: '/' })
    cookies.delete('primary_pilot', { path: '/' })

    return HTTP_200_Success(
        JSON.stringify({
            success: true,
            redirect: translatePath('/')
        })
    )
}