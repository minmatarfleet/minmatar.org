import { useTranslations } from '@i18n/utils';

const t = useTranslations('en');

import type { DoctrineType } from '@dtypes/layout_components'
import type { Doctrine } from '@dtypes/api.minmatar.org'
import { get_doctrines, get_doctrine_by_id } from '@helpers/api.minmatar.org/doctrines'
import { get_fitting_item } from '@helpers/fetching/ships'

export async function fetch_doctrines() {
    let api_doctrines:Doctrine[]

    api_doctrines = await get_doctrines()

    return await Promise.all(api_doctrines.map(async (doctrine) => {
        return {            
            id: doctrine.id,
            name: doctrine.name,
            description: doctrine.description,
            created_at: doctrine.created_at,
            updated_at: doctrine.updated_at,
            type: doctrine.type,
            primary_fittings: await Promise.all(doctrine.primary_fittings.map(async (fitting) => await get_fitting_item(fitting) )),
            secondary_fittings: await Promise.all(doctrine.secondary_fittings.map(async (fitting) => await get_fitting_item(fitting) )),
            support_fittings: await Promise.all(doctrine.support_fittings.map(async (fitting) => await get_fitting_item(fitting) )),
        } as DoctrineType
    }))
}

export async function fetch_doctrine_by_id(id:number) {
    let doctrine:Doctrine

    doctrine = await get_doctrine_by_id(id)

    return {            
        id: doctrine.id,
        name: doctrine.name,
        description: doctrine.description,
        created_at: doctrine.created_at,
        updated_at: doctrine.updated_at,
        type: doctrine.type,
        primary_fittings: await Promise.all(doctrine.primary_fittings.map(async (fitting) => await get_fitting_item(fitting) )),
        secondary_fittings: await Promise.all(doctrine.secondary_fittings.map(async (fitting) => await get_fitting_item(fitting) )),
        support_fittings: await Promise.all(doctrine.support_fittings.map(async (fitting) => await get_fitting_item(fitting) )),
    } as DoctrineType
}