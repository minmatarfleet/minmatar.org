import { useTranslations } from '@i18n/utils';

const t = useTranslations('en');

import type { FittingItem } from '@dtypes/layout_components'
import type { Fitting } from '@dtypes/api.minmatar.org'
import { get_fittings } from '@helpers/api.minmatar.org/ships'
import { get_ship_info } from '@helpers/sde/ships'

export async function fetch_fittings() {
    let api_fittings:Fitting[]

    api_fittings = await get_fittings()

    return await Promise.all(api_fittings.map(async (fitting) => {
        return await get_fitting_item(fitting)
    }))
}

export async function get_fitting_item(fitting:Fitting) {
    const ship_info = await get_ship_info(fitting.ship_id)

    return {
        fitting_name: fitting.name,
        fitting_type: parse_fitting_type(fitting.name),
        id: fitting.id,
        ship_id: fitting.ship_id,
        ship_name: ship_info?.name ?? t('error_ship_parsing'),
        ship_type: ship_info?.type ?? t('unknown'),
    } as FittingItem
}

const parse_fitting_type = (fitting_name:string) => {
    try {
        return fitting_name.split('[')[1].split(']')[0]
    } catch (error) {
        return t('fitting_type_error')
    }
}