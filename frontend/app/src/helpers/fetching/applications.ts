import { useTranslations } from '@i18n/utils';

const t = useTranslations('en');

import type { Corporation, CorporationApplicationDetails, EveCharacterProfile } from '@dtypes/api.minmatar.org'
import type { ApplicationOld, CorporationApplications, ApplicationBasic, ApplicationDetail, CorporationStatusType } from '@dtypes/layout_components'
import {
    get_corporation_applications,
    get_corporation_applications_by_id,
} from '@helpers/api.minmatar.org/applications'
import { get_user_character, get_users_character } from '@helpers/fetching/characters'
import { get_all_corporations } from '@helpers/api.minmatar.org/corporations'
import { unique_values } from '@helpers/array'

export async function get_all_applications(access_token:string) {
    let api_corporations:Corporation[]
    let applications:ApplicationOld[]

    api_corporations = await get_all_corporations('alliance')

    applications = (await Promise.all(api_corporations.map(async (corporation) => {
        let applications:ApplicationOld[] = []

        const api_applications = await get_corporation_applications(access_token, corporation.corporation_id)
        
        if (!api_applications || api_applications?.length === 0)
            return applications

        const users_ids = unique_values(api_applications.map(api_application => api_application.user_id))
        const character_profiles = await get_users_character(users_ids)

        applications = api_applications.map(application => {
            const character = character_profiles.find(character => character.user_id === application.user_id)

            return {
                id: application.application_id,
                applied_corporation: application.corporation_id, // django corporation id
                status: application.status,
                corporation_id: character?.corporation_id ?? 0,
                character_name: character?.character_name ?? t('unknown_character'),
                corporation_name: character?.corporation_name ?? t('unknown_corporation'),
            } as ApplicationOld
        })

        return applications
    }))).flat()

    applications = (await Promise.all(applications.map(async (application) => {
        let application_details:CorporationApplicationDetails
        application_details = await get_corporation_applications_by_id(access_token, application.corporation_id, application.id)

        application.description = application_details.description

        return application
    })))

    return applications
}

export async function get_all_corporations_applications(access_token:string, records:boolean = false) {
    let api_corporations:Corporation[]
    let applications:CorporationApplications[]

    api_corporations = await get_all_corporations('alliance')

    applications = (await Promise.all(api_corporations.map(async (corporation) => {
        const application:CorporationApplications = {
            corporation_id: corporation.corporation_id,
            corporation_name: corporation.corporation_name,
            applications: []
        }

        let api_applications = await get_corporation_applications(access_token, corporation.corporation_id)

        api_applications = api_applications.filter(application => {
            if (records && (application.status === 'accepted' || application.status === 'rejected'))
                return true

            if (!records && (application.status !== 'accepted' && application.status !== 'rejected'))
                return true

            return false
        })

        let character_profiles:EveCharacterProfile[] = []
        if (api_applications?.length > 0) {
            const not_null_applications = api_applications.filter(api_application => api_application)
            const users_ids = unique_values(not_null_applications.map(api_application => api_application?.user_id))
            character_profiles = users_ids.length > 0 ? await get_users_character(users_ids) : []
            character_profiles = character_profiles.filter(profile => profile)
        }

        application.applications = api_applications.map(application => {
            const character = character_profiles.find(character => character.user_id === application?.user_id)

            return {
                id: application.application_id,
                applied_corporation: application.corporation_id, // django corporation id
                character_id: character?.character_id ?? 0,
                character_name: character?.character_name ?? t('unknown_character'),
                corporation_id: character?.corporation_id ?? 0,
                corporation_name: character?.corporation_name ?? t('unknown_corporation'),
                status: application.status,
            } as ApplicationBasic
        })

        return application
    })))

    applications = applications.filter( (i) => i.applications.length > 0 )

    return applications
}

export async function get_application_by_id(access_token:string, corporation_id:number, application_id:number) {
    const api_application = await get_corporation_applications_by_id(access_token, corporation_id, application_id)

    const character = await get_user_character(api_application.user_id)

    return {
        id: api_application.application_id,
        applied_corporation: api_application.corporation_id,
        status: api_application.status as CorporationStatusType,
        character_id: character?.character_id ?? 0,
        character_name: character?.character_name ?? t('unknown_character'),
        corporation_id: character?.corporation_id ?? 0,
        corporation_name: character?.corporation_name ?? t('unknown_corporation'),
        description: api_application.description,
        created_at: api_application.created_at,
        updated_at: api_application.updated_at,
        alts: api_application.characters.filter( (i) => i.character_id !== character?.character_id )
    } as ApplicationDetail
}