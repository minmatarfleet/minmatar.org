import { get_module_props } from '@helpers/sde/modules'
import { get_item_id, get_item_category } from '@helpers/sde/items'

import type { Module, ShipFitting } from '@dtypes/layout_components';
import { get_ship_fitting_capabilities } from '@helpers/sde/ships'
// import { cachePromise } from '@helpers/cache'

export async function parse_eft(fitting_eft: string) {
    type EFTSection = 'name' | 'low' | 'med' | 'high' | 'rigs' | 'subsystem' | 'skip-drones' | 'drones' | 'cargo'
    let EFTSections:EFTSection[] = [ 'name', 'low', 'med', 'high', 'rigs', 'subsystem', 'skip-drones', 'drones', 'cargo' ]
    let has_subsystem = false
    let ship_fitting:ShipFitting
    let section:EFTSection
    const TRANSLATE = {
        'low': 'low_slots',
        'med': 'med_slots',
        'high': 'high_slots',
        'rigs' :'rig_slots',
        'subsystem': 'subsystem_slots',
        'drones': 'drones',
        'cargo': 'cargohold',
    }

    const SHIP_SLOTS = {
        'high': 'High power',
        'med': 'Medium power',
        'low': 'Low power',
        'rigs': 'Rig Slot',
        'subsystem': 'Sub System',
    }

    const EMPTY_SLOTS_TAGS = {
        'low': '[Empty Low slot]',
        'med' : '[Empty Med slot]',
        'high' : '[Empty High slot]',
        'rigs' : '[Empty Rig slot]',
        'subsystem' : '[Empty Subsystem slot]',
    }

    const lines = fitting_eft.split('\n')
    for (let i in lines) {
        let line = lines[i]

        line = line.trim()

        if (!section && line.startsWith('[') && line.endsWith(']')) {
            const ship_name = line.slice(1,-1).split(',')[0].trim()

            const ship_capbalitities = await get_ship_fitting_capabilities(ship_name)

            ship_fitting = {
                name: line.slice(1,-1).split(',')[1].trim(),
                ship_name: ship_name,
                capabilities: ship_capbalitities
            }

            has_subsystem = ship_capbalitities?.subsystem_slots ? true : false
            
            if (!has_subsystem)
                EFTSections = EFTSections.filter( (section) => section !== 'subsystem' )

            section = 'name'
            continue
        }

        if (line === '') {
            if (section !== 'cargo')
                section = EFTSections[EFTSections.indexOf(section) + 1]
            
            continue
        }

        if (!section) continue

        let module_name:string = line.split(',')[0]

        if (section === 'drones' || section === 'cargo') {
            let words:string[] = line.split(' ')
            const inline_amount_string:string = words.pop()
            let amount:number = parseInt(inline_amount_string.substring(1))

            if (isNaN(amount)) {
                amount = 1
            } else {
                module_name = words.join(' ')
            }

            const item_id = await get_item_id(module_name)

            if (section === 'drones' && await get_item_category(item_id) !== 'Drone')
                section = 'cargo'

            if (!ship_fitting[TRANSLATE[section]])
                ship_fitting[TRANSLATE[section]] = []

            ship_fitting[TRANSLATE[section]].push({
                id: await get_item_id(module_name),
                name: module_name,
                amount: amount,
            })
        } else {
            if (section === 'name')
                section = 'low'

            if (!ship_fitting[TRANSLATE[section]])
                ship_fitting[TRANSLATE[section]] = []

            if (module_name === EMPTY_SLOTS_TAGS[section]) {
                ship_fitting[TRANSLATE[section]].push(null)
            } else {
                const module:Module = await get_module_props(module_name)

                if (module && (SHIP_SLOTS[section] !== module.slot_name))
                    throw new Error(`Error parsing EFT: Module "${module_name}" is not ${SHIP_SLOTS[section]}`);

                ship_fitting[TRANSLATE[section]].push(
                    module
                    ?
                    module
                    :
                    {
                        id: await get_item_id(module_name),
                        name: module_name,
                        meta_name: 'Tech I',
                        slot_name: SHIP_SLOTS[section],
                    }
                )
            }
        }
    }

    console.log('Done parsing eft')
    return ship_fitting
}

/*const cached_get_module_props = cachePromise(get_module_props)
const cached_get_item_id = cachePromise(get_item_id)*/