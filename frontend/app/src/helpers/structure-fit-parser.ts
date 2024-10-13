import inv_types from '@json/eve_sde/invTypes.json';
import { get_item_icon } from '@helpers/eve_image_server';

import type { FittingGroups, StructureFittable } from '@dtypes/layout_components';
import { is_of_structure_slots_type } from '@dtypes/layout_components';

import { group_by } from '@helpers/array';

export const parse_structure_fit = (structure_fit: string):FittingGroups[] => {
    const fitting_groups:FittingGroups[] = []

    const fittables:StructureFittable[] = parse_structure(structure_fit)
    let _array = Object.values(fittables)
    //let grouped = Object.groupBy(_array, ({ slot }) => slot);
    let grouped = group_by(_array, 'slot')

    for (let slot_name in grouped) {
        const group = grouped[slot_name]
        
        fitting_groups.push({
            name: slot_name,
            fittables: group
        })
    }

    return fitting_groups
}

const parse_structure = (fitting_eft: string) => {
    let fittable = []
    let current_group = 'Unknown'

    fitting_eft.split('\n').forEach((line) => {
        line = line.trim()

        if (line == '')
            return

        if (is_of_structure_slots_type(line)) {
            current_group = line
            return
        }

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
            image: get_item_icon(inv_types[fittable_name].typeID),
            slot: current_group
        }

        if (fittable[fittable_name]) {
            fittable[fittable_name].amount += parsed_fittable.amount
        } else {
            fittable[fittable_name] = parsed_fittable
        }
    })

    return fittable
}