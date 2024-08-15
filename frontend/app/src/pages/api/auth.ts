import { i18n } from '@helpers/i18n'
import type { User } from '@dtypes/jwt'
import * as jose from 'jose'
import { is_prod_mode } from '@helpers/env'
import { HTTP_200_Success, HTTP_404_Not_Found, HTTP_403_Forbidden } from '@helpers/http_responses'
import { delete_account } from '@helpers/api.minmatar.org/authentication'

export async function DELETE({ request, params, cookies }) {
    const { t, translatePath } = i18n(new URL(request.url))

    const auth_token = cookies.has('auth_token') ? cookies.get('auth_token').value : false
    const user:User | false = auth_token ? jose.decodeJwt(auth_token) as User : false

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