import type { CombatLogAnalysis, CombatLogMaxUI } from '@dtypes/layout_components'
import { analize_log, analize_zipped_log, get_log_by_id } from '@helpers/api.minmatar.org/combatlog'
import { generate_timeline } from '@helpers/date'
import { parse_damage_from_logs } from '@helpers/eve'
import { get_fitting_by_id } from '@helpers/api.minmatar.org/ships'

export async function fetch_combatlog_analysis(combatlog:string | Uint8Array, gzipped:boolean, access_token?:string, fitting_id?:number, fleet_id?:number) {
    const analysis = gzipped ? await analize_zipped_log(combatlog as Uint8Array, access_token, fitting_id, fleet_id) : await analize_log(combatlog as string)

    const start_time = analysis.times[0].name
    const end_time = analysis.times[analysis.times.length - 1].name

    const timeline = generate_timeline(start_time, end_time)
    const damage_in:number[] = []
    const damage_out:number[] = []

    const damage_time_in = {}
    const damage_time_out = {}
    analysis.times.forEach(tick => {
        damage_time_in[tick.name] = tick.damage_from
        damage_time_out[tick.name] = tick.damage_to 
    })

    timeline.forEach(tick => {
        damage_in.push(damage_time_in[tick] ?? 0)
        damage_out.push(damage_time_out[tick] ?? 0)
    })

    const enemies = await parse_damage_from_logs(analysis.enemies)
    const weapons = await parse_damage_from_logs(analysis.weapons)
    
    const max_from = analysis?.max_from ? {
        damage: analysis?.max_from.damage,
        entity: analysis?.max_from.entity,
        outcome: analysis?.max_from.outcome,
        weapon: analysis?.max_from.weapon,
    } as CombatLogMaxUI : null

    const max_to = analysis?.max_to ? {
        damage: analysis?.max_to.damage,
        entity: analysis?.max_to.entity,
        outcome: analysis?.max_to.outcome,
        weapon: analysis?.max_to.weapon,
    } as CombatLogMaxUI : null

    const fitting = analysis?.fitting_id > 0 ? await get_fitting_by_id(analysis?.fitting_id) : null
    const fleet = analysis?.fleet_id > 0 ? analysis?.fleet_id : null
    
    return {
        logged_events: analysis.logged_events,
        damage_done: analysis.damage_done,
        damage_taken: analysis.damage_taken,
        start: new Date(analysis.start),
        end: new Date(analysis.end),
        damage_in: damage_in,
        damage_out: damage_out,
        timeline: timeline,
        enemies: enemies,
        weapons: weapons,
        character_name: analysis.character_name,
        ...(fitting && { fitting }),
        ...(fleet_id && { fleet }),
        ...(max_from && { max_from }),
        ...(max_to && { max_to }),
    } as CombatLogAnalysis
}

export async function fetch_combatlog_by_id(access_token:string, log_id:number) {
    const analysis = await get_log_by_id(access_token, log_id)

    const start_time = analysis.times[0].name
    const end_time = analysis.times[analysis.times.length - 1].name

    const timeline = generate_timeline(start_time, end_time)
    const damage_in:number[] = []
    const damage_out:number[] = []

    const damage_time_in = {}
    const damage_time_out = {}
    analysis.times.forEach(tick => {
        damage_time_in[tick.name] = tick.damage_from
        damage_time_out[tick.name] = tick.damage_to 
    })

    timeline.forEach(tick => {
        damage_in.push(damage_time_in[tick] ?? 0)
        damage_out.push(damage_time_out[tick] ?? 0)
    })

    const enemies = await parse_damage_from_logs(analysis.enemies)
    const weapons = await parse_damage_from_logs(analysis.weapons)
    
    const max_from = analysis?.max_from ? {
        damage: analysis?.max_from.damage,
        entity: analysis?.max_from.entity,
        outcome: analysis?.max_from.outcome,
        weapon: analysis?.max_from.weapon,
    } as CombatLogMaxUI : null

    const max_to = analysis?.max_to ? {
        damage: analysis?.max_to.damage,
        entity: analysis?.max_to.entity,
        outcome: analysis?.max_to.outcome,
        weapon: analysis?.max_to.weapon,
    } as CombatLogMaxUI : null

    const fitting = analysis?.fitting_id > 0 ? await get_fitting_by_id(analysis?.fitting_id) : null
    const fleet_id = analysis?.fleet_id > 0 ? analysis?.fleet_id : null
    
    return {
        logged_events: analysis.logged_events,
        damage_done: analysis.damage_done,
        damage_taken: analysis.damage_taken,
        start: new Date(analysis.start),
        end: new Date(analysis.end),
        damage_in: damage_in,
        damage_out: damage_out,
        timeline: timeline,
        enemies: enemies,
        weapons: weapons,
        character_name: analysis.character_name,
        ...(fitting && { fitting }),
        ...(fleet_id && { fleet_id }),
        ...(max_from && { max_from }),
        ...(max_to && { max_to }),
    } as CombatLogAnalysis
}