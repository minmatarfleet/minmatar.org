import type { ShipInfo } from '@dtypes/layout_components'
import models from '@/data/ccpwgl_object_models.json';

export const parse_faction_ship_name = (ship_info:ShipInfo) => {
    const FACTION_SUFIX = {
        'Amarr': 'Navy Issue',
        'Minmatar': 'Fleet Issue',
        'Gallente': 'Navy Issue',
        'Caldari': 'Navy Issue',
    }

    return ship_info.name.split(FACTION_SUFIX[ship_info.race] ?? '')[0].trim()
}

export const get_ship_dna = (ship_info:ShipInfo) => {
    const SKIN_SUFIX = {
        'Tech I': 'base',
        'Faction': 'navy',
        'Tech II': 'story',
    }

    let ship_name = ship_info.name
    const skin = ship_info.race.toLowerCase().concat(SKIN_SUFIX[ship_info.meta])
    const race = ship_info.race.toLowerCase()

    if (ship_info.meta === 'Faction')
        ship_name = parse_faction_ship_name(ship_info)

    const model = models[ship_name]

    if (!model || !skin || !race)
        return null

    return `${model}:${skin}:${race}`
}