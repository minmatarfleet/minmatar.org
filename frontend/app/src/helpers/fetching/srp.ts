import { useTranslations } from '@i18n/utils';
const t = useTranslations('en');

import type { SRPUI, FleetSRPUI } from '@dtypes/layout_components'
import type { SRP, SRPStatus } from '@dtypes/api.minmatar.org'
import { get_fleet_srp } from '@helpers/api.minmatar.org/srp'
import { unique_values } from '@helpers/array'

export async function fetch_srps(access_token:string, status:SRPStatus = 'pending') {
    let api_fleet_srps:SRP[]

    api_fleet_srps = await get_fleet_srp(access_token, { status: status})
    const fleet_ids = unique_values(api_fleet_srps.map(srp => srp.fleet_id))
    const fleets_srps = fleet_ids.map(fleet_id => {
        return {
            fleet_id: fleet_id,
            srps: api_fleet_srps.filter(srp => srp.fleet_id === fleet_id)
        } as FleetSRPUI
    })

    return fleets_srps
}

export async function fetch_fleet_srps(access_token:string, fleet_id: number, status:SRPStatus = 'pending') {
    let api_fleet_srps:SRP[]

    api_fleet_srps = await get_fleet_srp(access_token, { fleet_id: fleet_id, status: status})

    return api_fleet_srps as SRPUI[]
}