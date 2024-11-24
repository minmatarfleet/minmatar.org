import { useTranslations } from '@i18n/utils';
const t = useTranslations('en');

import type { SRPUI } from '@dtypes/layout_components'
import type { SRP, SRPStatus } from '@dtypes/api.minmatar.org'
import { get_fleet_srp } from '@helpers/api.minmatar.org/srp'

export async function fetch_fleet_srps(access_token:string, fleet_id: number, status:SRPStatus = 'pending') {
    let api_fleet_srps:SRP[]

    api_fleet_srps = await get_fleet_srp(access_token, fleet_id, status)

    return api_fleet_srps as SRPUI[]
}