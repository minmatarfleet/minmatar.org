/**
 * Labels for task rows: the one "when" line a row shows, the glyph for an
 * automatic task, and dates in EVE time.
 */
import type { TaskItem } from '@dtypes/api.minmatar.org'
import type { i18n } from '@helpers/i18n'

type Translate = ReturnType<typeof i18n>['t']

const HOUR = 60 * 60 * 1000
const DAY = 24 * HOUR

/** "Fri 20 Nov", in EVE time. */
export function task_date(value:string | Date, lang:string):string {
    const date = typeof value === 'string' ? new Date(value.length === 10 ? `${value}T12:00:00Z` : value) : value
    const parts = new Intl.DateTimeFormat(lang, {
        weekday: 'short',
        day: 'numeric',
        month: 'short',
        timeZone: 'UTC',
    }).formatToParts(date)
    const part = (type:string) => parts.find((item) => item.type === type)?.value ?? ''
    return `${part('weekday')} ${part('day')} ${part('month')}`
}

/** "Thursday", for "Repeats every Thursday" (recurrence "weekly:3"). */
export function recurrence_day(recurrence:string, lang:string):string | null {
    const match = /^weekly:(\d)$/.exec(recurrence)
    if (!match) return null
    // 2024-01-01 was a Monday, the API's day 0.
    const monday = Date.UTC(2024, 0, 1)
    return new Intl.DateTimeFormat(lang, { weekday: 'long', timeZone: 'UTC' })
        .format(new Date(monday + parseInt(match[1]) * DAY))
}

export function waiting_label(t:Translate, opened_at:string, now:Date = new Date()):string {
    const waited = now.getTime() - new Date(opened_at).getTime()
    if (waited >= DAY)
        return t('tasks.when.waiting_days').replace('~N', String(Math.floor(waited / DAY)))
    if (waited >= HOUR)
        return t('tasks.when.waiting_hours').replace('~N', String(Math.floor(waited / HOUR)))
    return t('tasks.when.just_now')
}

/** The single "when" cell of a row. */
export function when_label(t:Translate, lang:string, task:TaskItem, now:Date = new Date()):string {
    if (task.status !== 'open')
        return task.closed_at ? t('tasks.when.closed').replace('~DATE', task_date(task.closed_at, lang)) : ''
    if (task.waiting_on)
        return t('tasks.when.waiting_on').replace('~TITLE', task.waiting_on.title)
    if (task.due_date)
        return t('tasks.when.due').replace('~DATE', task_date(task.due_date, lang))
    if (task.when === 'no_rush')
        return t('tasks.when.no_rush')
    return waiting_label(t, task.opened_at, now)
}

/** One line under the title: what the site said, who asked, or the team. */
export function sub_label(t:Translate, task:TaskItem, team_label:string, in_project:boolean = false):string {
    const parts:string[] = []
    if (task.team_kind) {
        if (team_label) parts.push(team_label)
        if (!task.assignee) parts.push(t('tasks.up_for_grabs'))
    }
    if (task.detail) parts.push(task.detail)
    else if (!in_project && task.created_by && task.kind === 'assigned' && task.created_by.user_id !== task.assignee?.user_id)
        parts.push(t('tasks.asked_by').replace('~NAME', task.created_by.name))
    else if (in_project && task.assignee && !task.team_kind)
        parts.push(task.assignee.name)
    if (task.project_name && !in_project) parts.push(task.project_name)
    if (task.status === 'done' && task.thanked_by)
        parts.push(t('tasks.thanked_by').replace('~NAME', task.thanked_by.name))
    if (task.status !== 'open' && task.close_note && !task.thanked_by && parts.length === 0)
        parts.push(task.close_note)
    return parts.join(' · ')
}

/** Stroke icon paths (24×24) for automatic tasks, by rule. */
const GLYPHS:Record<string, string> = {
    reauth_character: 'M8 19a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM11 12l9-9M16 7l3 3',
    pick_main: 'M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM5 20c0-4 3-6 7-6s7 2 7 6',
    fleet_invite: 'M4 6h16v12H4zM4 7l8 6 8-6',
    tribe_invitation: 'M4 6h16v12H4zM4 7l8 6 8-6',
    set_timezone: 'M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18zM12 7v5l3 2',
    review_join_requests: 'M9 11a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM3 20c0-3 3-5 6-5s6 2 6 5M16 5a3 3 0 0 1 0 6M21 20c0-2-1-4-3-5',
    review_applications: 'M9 11a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM3 20c0-3 3-5 6-5s6 2 6 5M16 5a3 3 0 0 1 0 6M21 20c0-2-1-4-3-5',
    review_doctrine_changes: 'M4 7l2 2 3-4M4 15l2 2 3-4M13 8h7M13 16h7',
    approve_reddit_posts: 'M5 4h14v17H5zM9 9h6M9 13h6M9 17h3',
    map_payout_codes: 'M9 4 7 20M17 4l-2 16M4 9h16M3 15h16',
    fix_calendar_feeds: 'M4 5h16v15H4zM4 10h16M8 3v4M16 3v4',
    update_scopes: 'M4 12a8 8 0 0 1 14-5.3M20 12a8 8 0 0 1-14 5.3M18 3v4h-4M6 21v-4h4',
    corp_director_token: 'M8 19a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM11 12l9-9M16 7l3 3',
    corp_unlinked: 'M4 6h16v12H4zM4 7l8 6 8-6',
}

const ASSIGNED_GLYPH = 'M5 12l5 5 9-10'
const DONE_GLYPH = 'M5 12l5 5 9-10'

export function task_glyph(task:TaskItem):string {
    if (task.status === 'done') return DONE_GLYPH
    return GLYPHS[task.rule] ?? ASSIGNED_GLYPH
}

/** The row's picture: the person it is about when there is one. */
export function task_person(task:TaskItem, in_project:boolean = false) {
    if (in_project) return task.assignee
    if (task.kind === 'assigned' && task.created_by && task.created_by.user_id !== task.assignee?.user_id)
        return task.created_by
    if (task.team_kind && task.assignee)
        return task.assignee
    return null
}
