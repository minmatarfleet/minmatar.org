
import type { CombatLog } from '@dtypes/api.minmatar.org'
import type { CombatLogAnalysis, Damage } from '@dtypes/layout_components'
import { analize_log } from '@helpers/api.minmatar.org/combatlog'
import { generate_timeline } from '@helpers/date'
import { parse_damage_from_logs, parse_weapon_damage_from_logs } from '@helpers/eve'

export async function fetch_combatlog_analysis(combatlog:string) {
    const analysis = await analize_log(combatlog)

    const start_time = Object.keys(analysis.damage_time_in)[0]
    const end_time = Object.keys(analysis.damage_time_in)[Object.keys(analysis.damage_time_in).length - 1]

    const timeline = generate_timeline(start_time, end_time)
    const damage_in:number[] = []
    const damage_out:number[] = []

    timeline.forEach(tick => {
        damage_in.push(analysis.damage_time_in[tick] ?? 0)
        damage_out.push(analysis.damage_time_out[tick] ?? 0)
    })

    const damage_from_enemies = await parse_damage_from_logs(analysis.damage_from_enemies)
    const damage_to_enemies = await parse_damage_from_logs(analysis.damage_to_enemies)
    const damage_with_weapons = await parse_weapon_damage_from_logs(analysis.damage_with_weapons)
    
    return {
        logged_events: analysis.logged_events,
        damage_done: analysis.damage_done,
        damage_taken: analysis.damage_taken,
        start: new Date(start_time),
        end: new Date(end_time),
        damage_in: damage_in,
        damage_out: damage_out,
        timeline: timeline,
        damage_from_enemies: damage_from_enemies,
        damage_to_enemies: damage_to_enemies,
        damage_with_weapons: damage_with_weapons,
    } as CombatLogAnalysis
}