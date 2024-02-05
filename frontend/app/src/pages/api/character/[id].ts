
import { useTranslations } from '@i18n/utils';

import type { JWTCookies, JWT } from '@dtypes/jwt'
import * as jose from 'jose'

import { is_prod_mode } from '@helpers/env'

import { HTTP_200_Success, HTTP_404_Not_Found, HTTP_403_Forbidden } from '@helpers/http_responses'

import { delete_characters } from '@helpers/api.minmatar.org'

export async function DELETE({ params, cookies }) {
    const character_id = params.id
    const lang = params.lang ?? 'en'
    const t = useTranslations(lang)

    const auth_token = cookies.has('auth_token') ? cookies.get('auth_token').value : false
    const claim:JWTCookies | false = auth_token ? jose.decodeJwt(auth_token) as JWT : false

    if (!auth_token || !claim) {
        return HTTP_403_Forbidden()
    }

    let delete_character_error = false
    let status = false
    try {
        status = await delete_characters(auth_token, character_id)
    } catch (error) {
        delete_character_error = (is_prod_mode() ? t('delete_character_error') : error.message)
    }

    console.log(delete_character_error)

    if (!status)
        return HTTP_404_Not_Found()

    return HTTP_200_Success(true)
}