import { useTranslations } from '@i18n/utils';

import { prod_error_messages } from '@helpers/env'
import type { CorporationMembers, SelectOptions, MemberStatus } from '@dtypes/layout_components'
import { get_all_corporations_members } from '@helpers/fetching/corporations'

import { get_corporation_logo } from '@helpers/eve_image_server';

export interface CorporationsMembersData {
    corporations_members?:          CorporationMembers[];
    main_count?:                    number;
    alliance_members_count?:        number;
    unregistered_count?:            number;
    corporations_unfiltered?:       {};
    corporations_members_count?:    {};
    total_members?:                 number;
    corporations_options?:          SelectOptions[];
}

export async function get_corporations_members_data(auth_token:string, lang:'en' = 'en', status:MemberStatus = 'registered') {
    const t = useTranslations(lang);

    let corporations_members:CorporationMembers[] = []
    let main_count = 0
    let unregistered_count = 0
    let alliance_members_count = 0

    try {
        corporations_members = await get_all_corporations_members(auth_token as string)

        corporations_members.sort( (a, b) => {
            return b.members.length - a.members.length
        })

        corporations_members = corporations_members.map( (corporation) => {
            alliance_members_count += corporation.members.length
            main_count += corporation.members.filter( (member) => member.is_main && member.registered ).length

            const unregistered_members = corporation.members.filter( (member) => !member.registered && !member.exempt )

            if (status === 'unregistered')
                corporation.members = unregistered_members
            
            unregistered_count += unregistered_members.length

            return corporation
        })

        corporations_members = corporations_members.filter( (corporation) => corporation.members.length > 0 )
    } catch (error) {
        throw new Error(prod_error_messages() ? t('get_all_corporations_members_error') : error.message)
    }

    let total_members = 0
    const corporations_unfiltered = {}
    corporations_members.forEach( (corporation) => {
        corporations_unfiltered[corporation.corporation_id] = corporation.members.map( (member) => member.character_id )
        total_members += corporation.members.length
    })

    const corporations_members_count = {}
    corporations_members.forEach( (corporation) => {
        corporations_members_count[corporation.corporation_id] = corporation.members.length
    })

    const corporations_options = corporations_members.map( (corporation):SelectOptions => {
        return {
            value: corporation.corporation_id,
            label: corporation.corporation_name,
            image: get_corporation_logo(corporation.corporation_id, 32),
        }
    } )

    return {
        corporations_members: corporations_members,
        main_count: main_count,
        alliance_members_count: alliance_members_count,
        unregistered_count: unregistered_count,
        corporations_unfiltered: corporations_unfiltered,
        corporations_members_count: corporations_members_count,
        total_members: total_members,
        corporations_options: corporations_options,
    } as CorporationsMembersData
}