import { useTranslations, useTranslatedPath } from '@i18n/utils';
import type { User } from '@dtypes/jwt'
import * as jose from 'jose'
import { is_prod_mode } from '@helpers/env'
import { HTTP_200_Success, HTTP_404_Not_Found, HTTP_403_Forbidden } from '@helpers/http_responses'
import { delete_characters } from '@helpers/api.minmatar.org/characters'

export async function DELETE({ params, cookies, redirect }) {
    const character_id = params.id
    const lang = params.lang ?? 'en'
    const t = useTranslations(lang)
    const translatePath = useTranslatedPath(lang)

    const auth_token = cookies.has('auth_token') ? cookies.get('auth_token').value : false
    const user:User | false = auth_token ? jose.decodeJwt(auth_token) as User : false

    if (!auth_token || !user) {
        return HTTP_403_Forbidden()
    }

    let delete_character_error = false
    let status = false
    try {
        status = await delete_characters(auth_token, character_id)
    } catch (error) {
        delete_character_error = (is_prod_mode() ? t('delete_character_error') : error.message)
    }

    if (!status)
        return HTTP_404_Not_Found()

    const primary_character = cookies.has('primary_pilot') ? JSON.parse(cookies.get('primary_pilot').value) : null
    const primary_character_id = primary_character ? parseInt(primary_character.character_id) : null

    if (character_id == primary_character_id) {
        cookies.delete('primary_pilot', { path: '/' })

        return redirect(translatePath(`/partials/pilots_list_component?redirect=${translatePath('/account')}`))
        /*return HTTP_200_Success(
            JSON.stringify({
                success: true,
                redirect: translatePath('/account')
            })
        )*/
    }
    
    return redirect(translatePath(`/partials/pilots_list_component`))
}