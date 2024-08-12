import { useTranslations } from '@i18n/utils';

import { prod_error_messages } from '@helpers/env'
import type { CorporationApplications, SelectOptions } from '@dtypes/layout_components'
import { get_all_corporations_applications } from '@helpers/fetching/applications'

export interface ApplicationsData {
    corporations_applications?:         CorporationApplications[];
    corporations_unfiltered?:           CorporationApplications[];
    corporations_applications_count?:   number[];
    total_applications?:                number;
    corporations_options?:              SelectOptions[];
}

export async function get_applications_data(auth_token:string, lang:'en' = 'en') {
    const t = useTranslations(lang);

    let corporations_applications:CorporationApplications[] = []

    try {
        corporations_applications = await get_all_corporations_applications(auth_token as string)
        corporations_applications.sort( (a, b) => {
            return b.applications.length - a.applications.length
        })
    } catch (error) {
        throw new Error(prod_error_messages() ? t('get_all_corporations_applications_error') : error.message)
    }

    let total_applications = 0
    const corporations_unfiltered = {}
    corporations_applications.forEach( (corporation) => {
        corporations_unfiltered[corporation.corporation_id] = corporation.applications.map( (application) => application.id )
        total_applications += corporation.applications.length
    })

    const corporations_applications_count = {}
    corporations_applications.forEach( (corporation) => {
        corporations_applications_count[corporation.corporation_id] = corporation.applications.length
    })

    const corporations_options = corporations_applications.map( (corporation):SelectOptions => {
        return {
            value: corporation.corporation_id,
            label: corporation.corporation_name,
        }
    } )

    return {
        corporations_applications: corporations_applications,
        corporations_unfiltered: corporations_unfiltered,
        corporations_applications_count: corporations_applications_count,
        total_applications: total_applications,
        corporations_options: corporations_options,
    } as ApplicationsData
}