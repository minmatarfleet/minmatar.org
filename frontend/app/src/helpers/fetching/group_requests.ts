import { useTranslations } from '@i18n/utils';

const t = useTranslations('en');

import { cacheFn } from '@helpers/cache'
import type { Group, GroupRequest, UserProfile } from '@dtypes/api.minmatar.org'
import type { GroupRequestUI } from '@dtypes/layout_components'
import { get_available_groups, get_group_requests } from '@helpers/api.minmatar.org/groups'
import { get_user_by_id } from '@helpers/api.minmatar.org/authentication'

export async function get_group_requests_for_group_requests_list(access_token:string) {
    let groups:Group[] = []
    let requests:GroupRequestUI[][]

    groups = await get_available_groups(access_token)

    requests = await Promise.all(groups.map(async (request) => get_group_request(access_token, request)));

    return requests.flat()
}

const get_group_request = async (access_token:string, group:Group) => {
    let api_requests:GroupRequest[]
    let requests:GroupRequestUI[]

    api_requests = await get_group_requests(access_token, group.id)

    requests = await Promise.all(api_requests.map(async (api_request) => {
        let request:GroupRequestUI
        let user_profile:UserProfile
        
        user_profile = await cached_get_user_info(access_token, api_request.user)

        request = {
            group_id: group.id,
            group_name: group.name,
            character_id: user_profile.eve_character_profile.character_id,
            character_name: user_profile.eve_character_profile.character_name,
            corporation_id: user_profile.eve_character_profile.corporation_id,
            corporation_name: user_profile.eve_character_profile.corporation_name,
        }

        return request
    }));

    return requests
}

const get_user_info = async (access_token:string, user_id:number) => {
    let user_profile:UserProfile

    user_profile = await get_user_by_id(access_token, user_id)

    return user_profile
}

const cached_get_user_info = cacheFn(get_user_info)