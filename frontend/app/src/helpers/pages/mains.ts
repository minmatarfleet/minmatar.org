import { useTranslations } from '@i18n/utils';

import { prod_error_messages } from '@helpers/env'

import type { CorporationMembers, MainCharacters, SelectOptions } from '@dtypes/layout_components'
import { get_all_corporations_members } from '@helpers/fetching/corporations'

export interface MainsData {
    mains_alts?:                MainCharacters[];
    main_count?:                number;
    alliance_members_count?:    number;
    unregistered_count?:        number;
    mains_unfiltered?:          {};
    mains_alts_count?:          {};
    total_alts?:                number;
    mains_options?:             SelectOptions[];
}

export async function get_mains_data(auth_token:string, lang:'en' = 'en') {
    const t = useTranslations(lang)

    let corporations_members:CorporationMembers[] = []
    let mains_alts:MainCharacters[] = []
    let unregistered_count = 0
    let alliance_members_count = 0

    try {
        corporations_members = await get_all_corporations_members(auth_token as string)
        
        corporations_members.sort( (a, b) => {
            return b.members.length - a.members.length
        })

        corporations_members = corporations_members.map( (corporation) => {
            alliance_members_count += corporation.members.length

            corporation.members.filter( (member) => {
                if (member.is_main) {
                    mains_alts.push({
                        character_id: member.character_id,
                        character_name: member.character_name,
                        corporation_id: corporation.corporation_id,
                        corporation_name: corporation.corporation_name,
                        registered: member.registered,
                        alts: [],
                    })
                }

                return member.is_main 
            }).length

            corporation.members.map( (member) => {
                if (!member.is_main) {
                    mains_alts.map( (main) => {
                        if (main.character_id === member?.main_character?.character_id) {
                            member.corporation_id = corporation.corporation_id
                            member.corporation_name = corporation.corporation_name
                            main.alts.push(member)
                        }

                        return main
                    })
                }

                return member.is_main 
            }).length

            const unregistered_members = corporation.members.filter( (member) => !member.registered && !member.exempt )
            
            unregistered_count += unregistered_members.length

            return corporation
        })
    } catch (error) {
        throw new Error(prod_error_messages() ? t('get_all_mains_alts_error') : error.message)
    }

    mains_alts.sort( (a, b) => a.character_name.localeCompare(b.character_name))
    mains_alts = mains_alts.filter( (main) => main.registered )

    const main_count = mains_alts.length

    let total_alts = 0
    const mains_unfiltered = {}
    mains_alts.forEach( (main) => {
        mains_unfiltered[main.character_id] = main.alts.map( (alt) => alt.character_id )
        total_alts += main.alts.length
    })

    const mains_alts_count = {}
    mains_alts.forEach( (main) => {
        mains_alts_count[main.character_id] = main.alts.length
    })

    const mains_options = mains_alts.map( (main):SelectOptions => {
        return {
            value: main.character_id,
            label: main.character_name,
        }
    } )

    return {
        mains_alts: mains_alts,
        main_count: main_count,
        alliance_members_count: alliance_members_count,
        unregistered_count: unregistered_count,
        mains_unfiltered: mains_unfiltered,
        mains_alts_count: mains_alts_count,
        total_alts: total_alts,
        mains_options: mains_options,
    } as MainsData
}