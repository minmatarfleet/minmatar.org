import { useTranslations } from '@i18n/utils';

const t = useTranslations('en');

import type { CombatLogAnalysis, CombatLogMaxUI, FleetCombatLog, FittingCombatLog, RepairsUI } from '@dtypes/layout_components'
import type { CombatLog, CombatLogStoreOptions } from '@dtypes/api.minmatar.org'
import { analize_log, get_log_by_id, get_saved_logs } from '@helpers/api.minmatar.org/combatlog'
import { generate_timeline } from '@helpers/date'
import { parse_damage_from_logs } from '@helpers/eve'
import { get_fitting_by_id } from '@helpers/api.minmatar.org/ships'
import { unique_values } from '@helpers/array'
import { get_users_character } from '@helpers/fetching/characters'
import { get_item_id } from '@helpers/sde/items'

const CAPSULE_TYPE_ID = 670

export async function fetch_combatlog_analysis(combatlog:string | Uint8Array, gzipped:boolean, store_options?:CombatLogStoreOptions) {
    const analysis = await analize_log(combatlog, gzipped, store_options)
    return process_analysis(analysis)
}

export async function fetch_combatlog_by_id(access_token:string, log_id:number) {
    const analysis = await get_log_by_id(access_token, log_id)
    return process_analysis(analysis)
}

async function process_analysis(analysis:CombatLog) {
    analysis.times = analysis.times.sort((a, b) => a.name.localeCompare(b.name))
    const start_time = analysis.times[0]?.name ?? analysis.start
    const end_time = analysis.times[analysis.times.length - 1]?.name ?? analysis.end

    const timeline = generate_timeline(start_time, end_time)
    const damage_in:number[] = []
    const damage_out:number[] = []
    const reps_out:number[] = []

    const damage_time_in = {}
    const damage_time_out = {}
    const reps_time_out = {}
    analysis.times.forEach(tick => {
        damage_time_in[tick.name] = tick.damage_from
        damage_time_out[tick.name] = tick.damage_to 
        reps_time_out[tick.name] = tick.reps_to 
    })

    timeline.forEach(tick => {
        damage_in.push(damage_time_in[tick] ?? 0)
        damage_out.push(damage_time_out[tick] ?? 0)
        reps_out.push(reps_time_out[tick] ?? 0)
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
    const repairs = await Promise.all(analysis.repairs.map(async repair => {
        const effective_reps = (repair.repairs_to * 100) / (repair.max_to * repair.cycles_to)

        return {
            name: repair.name,
            rep_type: repair.rep_type,
            cycles: repair.cycles_to,
            amount_repaired: repair.repairs_to,
            avg_cycle: repair.avg_to,
            max_cycle: repair.max_to,
            effective_reps: effective_reps,
            item_id: await get_item_id(repair.name.split(' [')[0].trim()) ?? CAPSULE_TYPE_ID,
        } as RepairsUI
    }))

    const repairs_modules = await Promise.all(analysis.rep_modules.map(async repair => {
        const effective_reps = (repair.repairs_to * 100) / (repair.max_to * repair.cycles_to)

        return {
            name: repair.name,
            cycles: repair.cycles_to,
            amount_repaired: repair.repairs_to,
            avg_cycle: repair.avg_to,
            max_cycle: repair.max_to,
            effective_reps: effective_reps,
            item_id: await get_item_id(repair.name.split(' [')[0]) ?? CAPSULE_TYPE_ID,
        } as RepairsUI
    }))

    console.log(repairs_modules)
    
    return {
        logged_events: analysis.logged_events,
        damage_done: analysis.damage_done,
        damage_taken: analysis.damage_taken,
        start: new Date(analysis.start),
        end: new Date(analysis.end),
        damage_in: damage_in,
        damage_out: damage_out,
        reps_out: reps_out,
        timeline: timeline,
        enemies: enemies,
        weapons: weapons,
        repairs: repairs,
        armor_repaired: analysis.armor_repaired,
        shield_repaired: analysis.shield_repaired,
        repairs_modules: repairs_modules,
        character_name: analysis.character_name,
        ...(fitting && { fitting }),
        ...(fleet_id && { fleet_id }),
        ...(max_from && { max_from }),
        ...(max_to && { max_to }),
    } as CombatLogAnalysis
}

export async function get_fleet_combatlogs(access_token:string, fleet_id:number) {
    const fleet_logs = await get_saved_logs(access_token as string, { fleet_id: fleet_id })
    const not_null_logs = fleet_logs.filter(fleet_log => fleet_log)
    const user_ids = unique_values(not_null_logs.map(log => log.user_id))
    const loggers = user_ids.length > 0 ? await get_users_character(user_ids) : []

    return fleet_logs.map(log => {
        const logger = loggers.find(log => log.user_id === log.user_id)

        return {
            id: log.id,
            uploaded_at: log.uploaded_at,
            user_id: log.user_id,
            character_name: log.character_name,
            system_name: log.system_name,
            logger: logger !== undefined ? {
                character_id: logger.character_id,
                character_name: logger.character_name,
                corporation: {
                    id: logger.corporation_id,
                    name: logger.corporation_name,
                }
            } : {
                character_id: 0,
                character_name: t('unknown_character')
            }
        } as FleetCombatLog
    })
}

export async function get_fitting_combatlogs(access_token:string, fitting_id:number) {
    const fitting_logs = await get_saved_logs(access_token as string, { fitting_id: fitting_id })
    const not_null_logs = fitting_logs.filter(fitting_log => fitting_log && fitting_log.fitting_id === fitting_id)
    const user_ids = unique_values(not_null_logs.map(log => log.user_id))
    const loggers = user_ids.length > 0 ? await get_users_character(user_ids) : []

    return fitting_logs.map(log => {
        const logger = loggers.find(log => log.user_id === log.user_id)

        return {
            id: log.id,
            uploaded_at: log.uploaded_at,
            user_id: log.user_id,
            character_name: log.character_name,
            system_name: log.system_name,
            logger: logger !== undefined ? {
                character_id: logger.character_id,
                character_name: logger.character_name,
                corporation: {
                    id: logger.corporation_id,
                    name: logger.corporation_name,
                }
            } : {
                character_id: 0,
                character_name: t('unknown_character')
            }
        } as FittingCombatLog
    })
}