import { useTranslations } from '@i18n/utils';

const t = useTranslations('en');

import type { Corporation, CorporationApplication, UserProfile } from '@dtypes/api.minmatar.org'
import type { CorporationObject } from '@dtypes/layout_components'
import { get_all_corporations, get_corporation_by_id } from '@helpers/api.minmatar.org/corporations'
import { get_corporation_applications } from '@helpers/api.minmatar.org/applications'
import { get_user_by_id } from '@helpers/api.minmatar.org/authentication'

export async function get_corporations_for_corporations_list(access_token:string, user_id: number) {
    let api_corporations:Corporation[] = []
    let corporations:CorporationObject[] = []

    api_corporations = await get_all_corporations(access_token, 'alliance')

    corporations = await Promise.all(api_corporations.map(async (i) => add_status_to_corporation(i, access_token, user_id) ));
    
    return corporations
}

/*export async function get_corporations_for_corporations_list(access_token:string, user_id: number) {
    let api_corporations:Corporation[] = []
    let corporations:CorporationObject[] = []

    api_corporations = await get_all_corporations(access_token)

    corporations = await Promise.all(api_corporations.map(async (i) => add_status_to_corporation(i, access_token, user_id)));
    
    return corporations
}*/

export async function get_corporation_for_corporations_list_by_id(access_token:string, corporation_id:number, user_id: number) {
    let api_corporation:Corporation
    let corporation:CorporationObject

    api_corporation = await get_corporation_by_id(access_token, corporation_id)

    corporation = await add_status_to_corporation(api_corporation, access_token, user_id)
    
    return corporation
}

const add_status_to_corporation = async (api_corporation:Corporation, access_token:string, user_id:number) => {
    let corporation_applications:CorporationApplication[]

    try {
        corporation_applications = await get_corporation_applications(access_token, api_corporation.corporation_id)
    } catch (error) {
        const corporation:CorporationObject = {
            corporation_id: api_corporation.corporation_id,
            corporation_name: api_corporation.corporation_name,
            alliance_id: api_corporation.alliance_id,
            alliance_name: api_corporation.alliance_name,
            corporation_type: api_corporation.corporation_type,
            status: 'error'
        }

        return corporation
    }
    
    const user_application = corporation_applications.filter((application) => {
        return application.user_id == user_id
    })
    
    const corporation:CorporationObject = {
        corporation_id: api_corporation.corporation_id,
        corporation_name: api_corporation.corporation_name,
        alliance_id: api_corporation.alliance_id,
        alliance_name: api_corporation.alliance_name,
        corporation_type: api_corporation.corporation_type,
    }

    if (user_application.length > 0)
        corporation.status = user_application[0].status

    return corporation
}

export async function get_user_corporation_id(access_token:string, user_id: number) {
    let user_profile:UserProfile
    user_profile = await get_user_by_id(access_token, user_id)
    return user_profile.eve_character_profile.corporation_id
}