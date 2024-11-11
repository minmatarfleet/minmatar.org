import type { CombatLogAnalysis } from '@dtypes/layout_components'
import { analize_log, analize_zipped_log } from '@helpers/api.minmatar.org/combatlog'
import { generate_timeline } from '@helpers/date'
import { parse_damage_from_logs } from '@helpers/eve'

export async function fetch_combatlog_analysis(combatlog:string | Uint8Array, gzipped:boolean) {
    console.log(combatlog)
    console.log(gzipped)
    const analysis = gzipped ? await analize_zipped_log(combatlog as Uint8Array) : await analize_log(combatlog as string)

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
    } as CombatLogAnalysis
}