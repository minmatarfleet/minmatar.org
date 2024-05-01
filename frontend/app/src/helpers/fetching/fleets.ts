import { useTranslations } from '@i18n/utils';
const t = useTranslations('en');

import type { FleetUI, FleetItem, DoctrineType } from '@dtypes/layout_components'
import type { EveCharacterProfile, Fleet } from '@dtypes/api.minmatar.org'
import { get_fleets, get_fleet_by_id } from '@helpers/api.minmatar.org/fleets'
import { get_user_character } from '@helpers/fetching/characters'
import { fetch_doctrine_by_id } from '@helpers/fetching/doctrines'

export async function fetch_fleets(access_token:string, upcoming:boolean = true) {
    let api_fleets_id:number[]

    api_fleets_id = await get_fleets(access_token, upcoming)

    return await Promise.all(api_fleets_id.map(async (fleet_id) => await add_fleet_info(access_token, fleet_id) ))
}

export async function add_fleet_info(access_token:string, fleet_id:number) {
    let fleet:Fleet 

    try {
        fleet = await get_fleet_by_id(access_token, fleet_id)
    } catch (error) {
        fleet = {
            id: fleet_id,
            doctrine_id: 0,
            fleet_commander: null,
            location: '',
            type: 'casual',
            description: '',
            start_time: new Date('2100-01-01')
        }
    }
        
    let character_profile:EveCharacterProfile
    if (fleet?.fleet_commander)
        character_profile = await get_user_character(fleet.fleet_commander)

    return {
        id: fleet.id,
        description: fleet.description,
        fleet_commander_id: character_profile?.character_id ?? 0,
        fleet_commander_name: character_profile?.character_name ?? t('not_available'),
        location: fleet.location,
        start_time: fleet.start_time,
        type: fleet.type,
    } as FleetItem
}

export async function fetch_fleet_by_id(access_token:string, fleet_id:number) {
    const fleet = await get_fleet_by_id(access_token, fleet_id)
        
    let character_profile:EveCharacterProfile
    if (fleet?.fleet_commander)
        character_profile = await get_user_character(fleet.fleet_commander)

    let doctrine:DoctrineType
    if (fleet?.doctrine_id)
        doctrine = await fetch_doctrine_by_id(fleet.doctrine_id)

    return {
        id: fleet.id,
        description: fleet.description,
        fleet_commander_id: character_profile.character_id,
        fleet_commander_name: character_profile?.character_name ?? t('unknown_character'),
        location: fleet.location,
        start_time: fleet.start_time,
        type: fleet.type,
        doctrine: doctrine,
    } as FleetUI
}