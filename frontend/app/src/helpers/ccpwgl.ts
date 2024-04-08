import type { ShipInfo } from '@dtypes/layout_components'
import models from '@/data/ccpwgl_object_models.json';
import amarr_t2_skins from '@/data/amarr_t2_skins.json';
import caldari_t2_skins from '@/data/caldari_t2_skins.json';
import gallente_t2_skins from '@/data/gallente_t2_skins.json';
import minmatar_t2_skins from '@/data/minmatar_t2_skins.json';
import skins from '@/data/skins.json';

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
    let skin
    if (ship_info.meta !== 'Tech II')
        skin = ship_info.race.toLowerCase().concat(SKIN_SUFIX[ship_info.meta])
    else {
        switch (ship_info.race) {
            case 'Amarr':
                skin = amarr_t2_skins[ship_name] ?? null
                break;
            case 'Caldari':
                skin = caldari_t2_skins[ship_name] ?? null
                break;
            case 'Gallente':
                skin = gallente_t2_skins[ship_name] ?? null
                break;
            case 'Minmatar':
                skin = minmatar_t2_skins[ship_name] ?? null
                break;
        }

        skin = skins[skin] ?? null
    }

    const race = ship_info.race.toLowerCase()

    if (ship_info.meta === 'Faction')
        ship_name = parse_faction_ship_name(ship_info)

    const model = models[ship_name]

    if (!model || !skin || !race)
        return null

    return `${model}:${skin}:${race}`
}