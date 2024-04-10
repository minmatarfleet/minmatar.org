import type { ShipInfo, Module } from '@dtypes/layout_components'
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

export async function get_ship_dna(ship_id:number, subsystems:Module[]) {
    const ship_info = await get_ship_info(ship_id)

    let ship_graphics = await get_ship_graphics(ship_id)

    if (ship_info.meta === 'Faction')
        ship_graphics.model = await get_navy_ship_model(ship_info)

    let t3_model:string[] = []
    if (ship_info.meta === 'Tech III' && ship_info.type === 'Strategic Cruiser') {
        const RACE_TOKEN = {
            amarr: 'asc1',
            caldari: 'csc1',
            gallente: 'gsc1',
            minmatar: 'msc1',
        }

        const race = ship_info.race.toLowerCase()

        for (let i in subsystems) {
            const subsystem = subsystems[i]
            const index = parseInt(i)
            
            if (index === 2)
                t3_model.push(`res:/dx9/model/ship/${race}/strategiccruiser/${RACE_TOKEN[race]}/${RACE_TOKEN[race]}_t3_s3v1/${RACE_TOKEN[race]}_t3_s3v1.red`)

            const ship_graphics = await get_ship_graphics(subsystem.id)
            
            let res = `res:/dx9/model/ship/${ship_graphics.race}/strategiccruiser/${RACE_TOKEN[ship_graphics.race]}/${ship_graphics.model}/${ship_graphics.model}.red`

            if (index >= 2)
                res = res.replaceAll(`s${index+1}`, `s${index+2}`)

            t3_model.push(res)
        }

        return t3_model
    }

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