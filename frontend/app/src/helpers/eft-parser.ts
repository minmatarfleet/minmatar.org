import dgm_effects from '@json/eve_sde/dgmEffects.json';
import dgm_type_effects from '@json/eve_sde/dgmTypeEffects.json';
import inv_categories from '@json/eve_sde/invCategories.json';
import inv_groups from '@json/eve_sde/invGroups.json';
import inv_types from '@json/eve_sde/invTypes.json';
import custom_group from '@json/eve_sde/customGroup.json';
import { get_item_icon } from '@helpers/eve_image_server';

import type { Fittable, FittingParsed } from '@dtypes/layout_components';

export const parse_eft = (fitting_eft: string) => {
    const fittables:Fittable[] = parse_fittables(fitting_eft)
    return group_fittables(fittables)
}

const get_category = (fittable: string) => {
    const groupID = inv_types[fittable]?.groupID ?? ''
    const categoryID = inv_groups[groupID]?.categoryID ?? ''
    return inv_categories[categoryID]?.categoryName ?? 'Unknown'
}

const get_slot_name = (module_name: string) => {
    const typeID = inv_types[module_name]?.typeID ?? ''
    const effectID = dgm_type_effects[typeID]?.effectID ?? ''
    return dgm_effects[effectID]?.displayName ?? 'Unknown'
}

const group_fittables = (fittables: Fittable[]) => {
    let fitting_parsed:FittingParsed = {}
    let is_cargo = false;

    for (let fitable_name in fittables) {
        const fittable = fittables[fitable_name]

        if (fitable_name == '===') {
            is_cargo = true;
            continue;
        }

        const category = get_category(fitable_name)

        let fittable_group = (category == 'Module' && is_cargo == false ? get_slot_name(fitable_name) : category);
        fittable_group = custom_group[fitable_name] ?? fittable_group;

        if (!fitting_parsed[fittable_group])
            fitting_parsed[fittable_group] = [];

        fitting_parsed[fittable_group].push(fittable)
    }

    return fitting_parsed
}

const parse_fittables = (fitting_eft: string) => {
    let fittable = []
    let empty_line = false;

    fitting_eft.split('\n').forEach((line) => {
        line = line.trim()

        if (line == '') {
            if (empty_line && !fittable['==='])
                fittable['==='] = 'Cargo starts here'

            empty_line = true;

            return
        } else {
            empty_line = false
        }

        if (line.startsWith('[') && line.endsWith(']'))
            return

        let fittable_name:string = line

        let words:string[] = line.split(' ')
        const inline_amount_string:string = words.pop() as string
        let amount:number = parseInt(inline_amount_string.substring(1))

        if (isNaN(amount)) {
            amount = 1
        } else {
            fittable_name = words.join(' ')
        }

        const parsed_fittable = {
            name: fittable_name,
            amount: amount,
            image: get_item_icon(inv_types[fittable_name].typeID)
        }

        if (fittable[fittable_name]) {
            fittable[fittable_name].amount += parsed_fittable.amount
        } else {
            fittable[fittable_name] = parsed_fittable
        }
    })

    return fittable
}