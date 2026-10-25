import { query_string } from '@helpers/string'

export const TRAINING_PARTIAL = '/partials/training_component/'
export const TRAINING_PLAN_PARTIAL = '/partials/training_plan_component/'
export const TRAINING_SHIPS_PARTIAL = '/partials/training_ships_component/'
export const TRAINING_MOVE_PARTIAL = '/partials/training_move_component/'

/** Ready ships shown in a character row before the "+N" chip. */
export const READY_ICONS = 6

export type TrainingMode =
    | 'add_goal'
    | 'remove_goal'
    | 'first'
    | 'target'
    | 'not_for_fleets'
    | 'for_fleets'
    | 'move'

export interface TrainingTime {
    key: 'training.under_hour' | 'training.hours' | 'training.day' | 'training.days'
    value: string
}

/** "under 1 h", "4 h", "1 day", "2.1 days": one number, rounded for reading. */
export function training_time(days:number):TrainingTime {
    const hours = days * 24
    if (hours < 1) return { key: 'training.under_hour', value: '' }
    if (Math.round(hours) < 24) return { key: 'training.hours', value: Math.round(hours).toString() }
    const rounded = Math.max(1, days < 10 ? Math.round(days * 10) / 10 : Math.round(days))
    if (rounded === 1) return { key: 'training.day', value: '1' }
    return { key: 'training.days', value: rounded.toString() }
}

/** Skill points as "58M" / "820k". */
export function short_skill_points(sp:number):string {
    if (sp >= 1_000_000) return `${Math.round(sp / 1_000_000)}M`
    if (sp >= 1_000) return `${Math.round(sp / 1_000)}k`
    return sp.toString()
}

const ROMAN = ['', 'I', 'II', 'III', 'IV', 'V']

export function skill_level(level:number):string {
    return ROMAN[level] ?? level.toString()
}

/** A partial URL with its query, for hx-get / hx-post and show_modal. */
export function training_url(base:string, params:Record<string, string | number | undefined>):string {
    const defined = Object.fromEntries(
        Object.entries(params)
            .filter(([, value]) => value !== undefined && value !== '')
            .map(([key, value]) => [key, String(value)])
    )
    const query = query_string(defined)
    return query ? `${base}?${query}` : base
}

/** training_time as text, with the page's `t`. */
export function time_label(t:(key:TrainingTime['key']) => string, days:number):string {
    const time = training_time(days)
    return t(time.key).replace('{value}', time.value)
}
