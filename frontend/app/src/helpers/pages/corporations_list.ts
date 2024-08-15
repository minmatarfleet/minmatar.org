import { useTranslations } from '@i18n/utils';

import { prod_error_messages } from '@helpers/env'
import type { CorporationObject } from '@dtypes/layout_components'
import { get_corporations_list, get_corporations_list_auth, get_user_corporation_id } from '@helpers/fetching/corporations'

export interface CorporationsListData {
    corporations?:          CorporationObject[];
    user_corporation_id?:   number;
}

export async function get_corporations_list_data(auth_token:string | null, lang:'en' = 'en', user_id:number | null) {
    const t = useTranslations(lang);
    let corporations:CorporationObject[] = []

    try {
        const user_corporation_id = (user_id ? await get_user_corporation_id(user_id) : null)

        if (auth_token && user_id)
            corporations = await get_corporations_list_auth(auth_token, user_id, 'alliance')
        else
            corporations = await get_corporations_list('alliance')

        return {
            corporations: corporations,
            user_corporation_id: user_corporation_id,
        } as CorporationsListData
    } catch (error) {
        throw new Error(prod_error_messages() ? t('get_all_corporations_error') : error.message)
    }
}