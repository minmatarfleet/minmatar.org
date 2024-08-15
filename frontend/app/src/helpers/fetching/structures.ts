import type { StructureTimerUI } from '@dtypes/layout_components'
import { get_structure_timers } from '@helpers/api.minmatar.org/structures'
import { get_structure_id } from '@helpers/eve'

export async function fetch_structure_timers(access_token:string, active:boolean = true) {
    const api_structure_timers = await get_structure_timers(access_token, active)

    return api_structure_timers.map((api_structure_timer) => {
        return {
            id: api_structure_timer.id,
            name: api_structure_timer.name,
            state: api_structure_timer.state,
            timer: api_structure_timer.timer,
            system_name: api_structure_timer.system_name,
            alliance_id: 1,
            alliance_name: api_structure_timer.alliance_name,
            corporation_name: api_structure_timer.corporation_name,
            structure_id: api_structure_timer.structure_id,
            structure_type: api_structure_timer.type,
            structure_type_id: get_structure_id(api_structure_timer.type),
            verified: api_structure_timer.updated_at !== null,
        } as StructureTimerUI
    })
}

export async function fetch_structure_timer_by_id(access_token:string, timer_id:number, active:boolean = true) {
    const api_structure_timer = (await get_structure_timers(access_token, active)).find((timer) => timer.id === timer_id)

    return api_structure_timer !== undefined ? {
        id: api_structure_timer.id,
        name: api_structure_timer.name,
        state: api_structure_timer.state,
        timer: api_structure_timer.timer,
        system_name: api_structure_timer.system_name,
        alliance_id: 1,
        alliance_name: api_structure_timer.alliance_name,
        corporation_name: api_structure_timer.corporation_name,
        structure_id: api_structure_timer.structure_id,
        structure_type: api_structure_timer.type,
        structure_type_id: get_structure_id(api_structure_timer.type),
        verified: api_structure_timer.updated_at !== null,
    } as StructureTimerUI : null
}