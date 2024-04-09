import type { ShipInfo } from '@dtypes/layout_components'
import { get_ship_graphics, get_ship_info } from '@helpers/sde/ships'
import { get_item_id } from '@helpers/sde/items'
import skin_translation from '@/data/skin_translation.json'

export const parse_faction_ship_name = (ship_info:ShipInfo) => {
    const FACTION_SUFIX = {
        'Amarr': 'Navy Issue',
        'Minmatar': 'Fleet Issue',
        'Gallente': 'Navy Issue',
        'Caldari': 'Navy Issue',
    }

    return ship_info.name.split(FACTION_SUFIX[ship_info.race] ?? '')[0].trim()
}

export async function get_ship_dna(ship_id:number) {
    const ship_info = await get_ship_info(ship_id)

    let ship_graphics = await get_ship_graphics(ship_id)

    if (ship_info.meta === 'Faction')
        ship_graphics.model = await get_navy_ship_model(ship_info)

    console.log(skin_translation)
    console.log(ship_graphics.skin)
    ship_graphics.skin = skin_translation[ship_graphics.skin] ?? ship_graphics.skin

    if (!ship_graphics.model || !ship_graphics.skin || !ship_graphics.race)
        return null

    return `${ship_graphics.model}:${ship_graphics.skin}:${ship_graphics.race}`
}

export async function get_navy_ship_model(ship_info:ShipInfo) {
    const base_ship_name = parse_faction_ship_name(ship_info)
    const base_ship_id = await get_item_id(base_ship_name)
    const ship_graphics = await get_ship_graphics(base_ship_id)

    return ship_graphics.model
}