import { useTranslations } from '@i18n/utils';

const t = useTranslations('en');

import type { DoctrineType, DoctrineTypes } from '@dtypes/layout_components'
import { doctrine_types } from '@dtypes/layout_components'
import type { Doctrine, Location } from '@dtypes/api.minmatar.org'
import { get_doctrines, get_doctrine_by_id } from '@helpers/api.minmatar.org/doctrines'
import { get_fitting_item } from '@helpers/fetching/ships'
import { get_groups } from '@helpers/fetching/groups'
import { get_locations_by_ids } from '@helpers/api.minmatar.org/locations'

function normalize_doctrine_type(type: string): DoctrineTypes {
    // If the type is one of the valid types, return it
    if (doctrine_types.includes(type as DoctrineTypes)) {
        return type as DoctrineTypes
    }
    // Otherwise, default to non_strategic
    return 'non_strategic'
}

export async function fetch_doctrines() {
    let api_doctrines:Doctrine[]

    api_doctrines = await get_doctrines()
    const sigs = await get_groups('group')

    // Collect all unique location_ids from all doctrines
    const all_location_ids: number[] = []
    api_doctrines.forEach(doctrine => {
        if (doctrine.location_ids && doctrine.location_ids.length > 0) {
            doctrine.location_ids.forEach(location_id => {
                if (!all_location_ids.includes(location_id)) {
                    all_location_ids.push(location_id)
                }
            })
        }
    })

    // Fetch all locations at once
    let locations_map: Map<number, Location> = new Map()
    if (all_location_ids.length > 0) {
        try {
            const locations = await get_locations_by_ids(all_location_ids)
            locations.forEach(location => {
                locations_map.set(location.location_id, location)
            })
        } catch (error) {
            console.error('Error fetching locations:', error)
        }
    }

    return await Promise.all(api_doctrines.map(async (doctrine) => {
        return {            
            id: doctrine.id,
            name: doctrine.name,
            description: doctrine.description,
            created_at: doctrine.created_at,
            updated_at: doctrine.updated_at,
            type: normalize_doctrine_type(doctrine.type),
            primary_fittings: await Promise.all(doctrine.primary_fittings.map(async (fitting) => await get_fitting_item(fitting) )),
            secondary_fittings: await Promise.all(doctrine.secondary_fittings.map(async (fitting) => await get_fitting_item(fitting) )),
            support_fittings: await Promise.all(doctrine.support_fittings.map(async (fitting) => await get_fitting_item(fitting) )),
            sigs: doctrine.sig_ids.map((sig_id) => {
                const sig = sigs.find((sig) => sig.id === sig_id)
                
                return {
                    id: sig?.id ?? 0,
                    name: sig?.name ?? t('unknown_sig'),
                    image_url: sig?.image_url,
                    description: sig?.description,
                }
            }),
            location_ids: doctrine.location_ids ?? []
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
        type: normalize_doctrine_type(doctrine.type),
        primary_fittings: await Promise.all(doctrine.primary_fittings.map(async (fitting) => await get_fitting_item(fitting) )),
        secondary_fittings: await Promise.all(doctrine.secondary_fittings.map(async (fitting) => await get_fitting_item(fitting) )),
        support_fittings: await Promise.all(doctrine.support_fittings.map(async (fitting) => await get_fitting_item(fitting) )),
        location_ids: doctrine.location_ids ?? []
    } as DoctrineType
}